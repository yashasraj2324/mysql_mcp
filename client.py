#!/usr/bin/env python3
"""
AI SQL Agent Client

This script creates an AI assistant that can interact with MySQL databases
using natural language. It uses OpenRouter API to translate natural language
to SQL and communicates with the MCP server to execute the queries.
"""

import os
import sys
import asyncio
import json
import logging
import requests
from typing import Dict, List, Any, Union, cast
from dataclasses import dataclass, field
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sql_agent_client")

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["./mcp_server.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)

@dataclass
class OpenRouterAgent:
    """OpenRouter AI agent for translating natural language to SQL"""
    
    # Chat history for context
    messages: List[Dict[str, Any]] = field(default_factory=list)
    
    # System prompt to guide the AI
    system_prompt: str = """You are a MySQL expert AI assistant that excels at translating natural language questions into valid SQL queries.

Your job is to:
1. Analyze the user's question and understand their intent
2. Generate a precise SQL query that answers their question based on the database schema
3. Explain the query in simple terms
4. Only return SQL for valid database requests

Always respond with only a JSON object that contains two fields:
1. "sql": The complete SQL query string (ending with a semicolon)
2. "explanation": A brief explanation of what the query does

For example:
```json
{
  "sql": "SELECT * FROM users WHERE age > 30 LIMIT 10;",
  "explanation": "This query retrieves all columns for up to 10 users who are older than 30 years."
}
```

Always use standard SQL syntax compatible with MySQL. Ensure your queries use only tables and columns from the database schema when it's provided."""
    
    def __init__(self):
        # OpenRouter API configuration
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.error("OpenRouter API key not found. Set OPENROUTER_API_KEY in .env file")
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-opus-20240229")
        
        # Initialize the message history with system prompt
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
    
    async def generate_sql(self, query: str, schema: str = "") -> Dict[str, Any]:
        """Generate SQL from natural language using OpenRouter API"""
        
        # Add schema information if available
        prompt = query
        if schema:
            prompt = f"Database Schema:\n{schema}\n\nBased on this schema, {query}"
        
        # Add the user message to history
        self.messages.append({"role": "user", "content": prompt})
        
        try:
            # Prepare the request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": self.messages,
                "temperature": 0.2,
                "max_tokens": 1024,
                "response_format": {"type": "json_object"}
            }
            
            # Call OpenRouter API
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract and parse response
            content = data["choices"][0]["message"]["content"]
            self.messages.append({"role": "assistant", "content": content})
            
            # Parse the JSON response
            result = json.loads(content)
            return result
            
        except requests.RequestException as e:
            logger.error(f"OpenRouter API request failed: {e}")
            return {
                "error": "Failed to connect to OpenRouter API",
                "details": str(e)
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response as JSON: {e}")
            return {
                "error": "Received invalid response format",
                "details": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "error": "Unexpected error occurred",
                "details": str(e)
            }

@dataclass
class SQLChat:
    """Main chat interface for the SQL agent"""
    
    # OpenRouter agent for SQL generation
    openrouter_agent: OpenRouterAgent = field(default_factory=OpenRouterAgent)
    
    async def get_database_schema(self, session: ClientSession) -> str:
        """Fetch the database schema using the MCP server tools"""
        try:
            schema_result = await session.call_tool("get_database_schema", {})
            return getattr(schema_result.content[0], "text", "")
        except Exception as e:
            logger.error(f"Failed to get database schema: {e}")
            return ""
    
    async def process_query(self, session: ClientSession, user_query: str) -> None:
        """Process a user query by generating SQL and executing it"""
        try:
            # Get database schema for context
            schema = await self.get_database_schema(session)
            
            # Generate SQL from the natural language query
            print(f"\n🤔 Generating SQL query for: '{user_query}'")
            sql_result = await self.openrouter_agent.generate_sql(user_query, schema)
            
            if "error" in sql_result:
                print(f"\n❌ Error: {sql_result['error']}")
                if "details" in sql_result:
                    print(f"Details: {sql_result['details']}")
                return
                
            # Extract the SQL query and explanation
            sql_query = sql_result.get("sql", "").strip()
            explanation = sql_result.get("explanation", "No explanation provided")
            
            if not sql_query:
                print("\n❌ Error: No SQL query was generated")
                return
                
            # Display the generated SQL and explanation
            print(f"\n💡 Generated SQL:")
            print(f"\033[1m{sql_query}\033[0m")
            print(f"\n📝 Explanation: {explanation}")
            
            # Execute the SQL query
            print("\n⚙️ Executing query...")
            result = await session.call_tool("query_data", {"sql": sql_query})
            query_result = getattr(result.content[0], "text", "")
            
            # Display the query results
            print("\n🔍 Result:")
            print(f"\033[92m{query_result}\033[0m")
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            print(f"\n❌ Error: An unexpected error occurred: {str(e)}")
    
    async def chat_loop(self, session: ClientSession):
        """Main chat loop for interacting with the user"""
        print("\n👋 Welcome to the AI SQL Agent!")
        print("Ask questions about your database in natural language, and I'll translate them to SQL and execute them.")
        print("Type 'exit' or 'quit' to end the session.\n")
        
        while True:
            try:
                # Get user input
                user_query = input("\n🔍 Ask a question: ").strip()
                
                # Check for exit command
                if user_query.lower() in ["exit", "quit", "bye"]:
                    print("\n👋 Goodbye!")
                    break
                    
                if not user_query:
                    continue
                    
                # Process the query
                await self.process_query(session, user_query)
                
            except KeyboardInterrupt:
                print("\n\n👋 Session interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Unexpected error in chat loop: {e}")
                print(f"\n❌ An unexpected error occurred: {str(e)}")
    
    async def run(self):
        """Run the SQL chat agent"""
        try:
            print("🚀 Starting AI SQL Agent...")
            print("📊 Connecting to MySQL database...")
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the connection
                    await session.initialize()
                    
                    # List available tools
                    tools_response = await session.list_tools()
                    logger.info(f"Available tools: {[t.name for t in tools_response.tools]}")
                    
                    # Start the chat loop
                    await self.chat_loop(session)
                    
        except KeyboardInterrupt:
            print("\n\n👋 Session interrupted. Goodbye!")
        except Exception as e:
            logger.error(f"Failed to run SQL agent: {e}")
            print(f"\n❌ Error: {str(e)}")

async def main():
    """Main entry point for the application"""
    try:
        chat = SQLChat()
        await chat.run()
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
