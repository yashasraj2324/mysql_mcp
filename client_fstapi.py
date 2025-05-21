

import os
import sys
import json
import logging
import requests
from typing import Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("sql_agent_api")

# MCP server params
server_params = StdioServerParameters(command=sys.executable, args=["./mcp_server.py"])

# FastAPI instance
app = FastAPI(title="AI SQL Agent API")


# ---------- Agent & Core Logic ---------- #

@dataclass
class OpenRouterAgent:
    messages: list[Dict[str, Any]] = field(default_factory=list)
    system_prompt: str = (
        "You are a MySQL expert AI assistant that translates natural language into SQL.\n"
        "Respond ONLY with a JSON object containing:\n"
        "1. \"sql\": The SQL query ending with a semicolon.\n"
        "2. \"explanation\": What the query does in simple language.\n"
        "Do not include any other commentary or text."
    )

    def __post_init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set.")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "meta-llama/llama-3.3-8b-instruct:free"
        self.messages.append({"role": "system", "content": self.system_prompt})

    async def generate_sql(self, query: str, schema: str = "") -> Dict[str, Any]:
        prompt = f"Database Schema:\n{schema}\n\n{query}" if schema else query
        self.messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": self.messages,
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        try:
            # Use asyncio.to_thread to call blocking requests.post in async context
            response = await asyncio.to_thread(
                lambda: requests.post(self.api_url, headers=headers, json=payload)
            )
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            self.messages.append({"role": "assistant", "content": content})

            # Remove markdown code blocks and whitespace
            cleaned = content.strip().strip("```").strip()
            return json.loads(cleaned)

        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            logger.error(f"OpenRouter API error or invalid response: {e}")
            return {"error": f"OpenRouter API error or invalid response: {e}"}


# ---------- FastAPI Models ---------- #

class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    sql: str
    explanation: str
    result: str


# ---------- Routes ---------- #

@app.get("/")
def root():
    return {"message": "AI SQL Agent API is up"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                schema_resp = await session.call_tool("get_database_schema", {})
                schema = ""
                if schema_resp.content and len(schema_resp.content) > 0:
                    # Defensive extraction - content is usually list of strings
                    schema = schema_resp.content[0] if isinstance(schema_resp.content[0], str) else ""

                logger.info(f"Database schema fetched for AI:\n{schema}")

                agent = OpenRouterAgent()
                ai_response = await agent.generate_sql(request.question, schema)

                if "error" in ai_response:
                    raise HTTPException(status_code=500, detail=ai_response["error"])

                if "sql" not in ai_response:
                    raise HTTPException(status_code=500, detail="Invalid AI response, missing SQL.")

                sql = ai_response["sql"].strip()
                explanation = ai_response.get("explanation", "").strip()

                logger.info(f"AI generated SQL:\n{sql}")

                query_result = await session.call_tool("query_data", {"sql": sql})

                result_text = ""
                if query_result.content and len(query_result.content) > 0:
                    result_obj = query_result.content[0]
                    # Extract .text attribute if it exists, else fallback to str()
                    result_text = getattr(result_obj, "text", None)
                    if result_text is None:
                        result_text = str(result_obj)

                return ChatResponse(sql=sql, explanation=explanation, result=result_text)

    except HTTPException as http_exc:
        logger.error(f"/chat HTTP error: {http_exc.detail}")
        raise http_exc

    except Exception as e:
        logger.error(f"/chat unexpected error: {e}", exc_info=True)
        return ChatResponse(sql="", explanation="", result=f"Error: {str(e)}")
