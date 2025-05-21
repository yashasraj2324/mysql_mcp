# AI SQL Agent
An AI-powered SQL agent that allows you to interact with MySQL databases using natural language queries. This tool translates English questions into SQL queries, executes them, and returns the results in a user-friendly format.

## Features
- 🗣️ **Natural Language Interface**: Query your database using plain English
- 🤖 **AI-Powered Translation**: Uses OpenRouter API to convert natural language to SQL
- 🔍 **Schema-Aware**: Takes database structure into account when generating queries
- 🛡️ **Safety Checks**: Prevents potentially dangerous operations
- 📊 **Formatted Results**: Clean display of query results
- 🌐 **REST API**: Access via HTTP endpoints using FastAPI

## Requirements
- Python 3.7+
- MySQL Database
- OpenRouter API key ([Get one here](https://openrouter.ai/keys))

## Installation
1. Clone this repository
   ```bash
   git clone [https://github.com/yashasraj2324/mysql_mcp.git]
   cd mysql_mcp
      ```
2. Run the setup script
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
3. Edit the `.env` file with your OpenRouter API key and MySQL credentials
   ```
   OPENROUTER_API_KEY=your_key_here
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_password
   MYSQL_DATABASE=your_database
   ```

## Usage

### Command Line Interface
1. Activate the virtual environment
   ```bash
   source venv/bin/activate
   ```
2. Run the command line application
   ```bash
   python mcp_client.py
   ```
3. Start asking questions about your database in natural language!

### REST API
1. Activate the virtual environment
   ```bash
   source venv/bin/activate
   ```
2. Run the API server
   ```bash
   uvicorn api:app --reload
   ```
3. Access the API at `http://localhost:8000`
   - Swagger documentation: `http://localhost:8000/docs`
   - ReDoc documentation: `http://localhost:8000/redoc`

### API Endpoints
- **GET /** - Check if API is running
- **POST /chat** - Submit a natural language query
  - Request body: `{"question": "Your question about the database"}`
  - Response: `{"sql": "Generated SQL", "explanation": "Plain English explanation", "result": "Query results"}`

### Example Queries
- "Show me the top 5 customers by purchase amount"
- "List all products that are out of stock"
- "What's the average order value in the last month?"
- "Find employees who haven't made a sale yet"
- "Count orders by status"

## How It Works
The system uses a client-server architecture with three main components:

1. **MCP Client (mcp_client.py)**
   - Manages the chat interface
   - Uses OpenRouter API to translate natural language to SQL
   - Communicates with the MCP server to execute queries

2. **MCP Server (mcp_server.py)**
   - Connects to your MySQL database
   - Provides tools for database operations
   - Executes SQL queries and returns results

3. **API Server (api.py)**
   - Provides HTTP endpoints for remote access
   - Communicates with the MCP server
   - Returns results in JSON format

The communication flow is:
```
User Question → OpenRouter NL→SQL Translation → SQL Query → MySQL Database → Results → User
```

## Customization

### Changing the AI Model
You can change the OpenRouter model by editing the `OPENROUTER_MODEL` variable in your `.env` file. Available options include:
- `anthropic/claude-3-opus-20240229` (default)
- `openai/gpt-4-turbo`
- `anthropic/claude-3-5-sonnet-20240620`
- `anthropic/claude-3-haiku-20240307`

For the API, you can change the model in the `OpenRouterAgent` class in `api.py`.

### Adjusting System Prompts
You can modify the system prompt in `mcp_client.py` or `api.py` to change how the AI generates SQL queries.

## Deployment
For production deployment:

1. Run with Gunicorn
   ```bash
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker api:app
   ```

2. Or deploy with Docker (see Dockerfile in repo)
   ```bash
   docker build -t ai-sql-agent .
   docker run -p 8000:8000 ai-sql-agent
   ```

## Troubleshooting

### Connection Issues
- Make sure your MySQL credentials are correct in the `.env` file
- Check that your MySQL server is running and accessible

### API Key Issues
- Verify your OpenRouter API key is correct
- Ensure you have sufficient credits in your OpenRouter account

### SQL Generation Issues
- Try to be more specific in your questions
- Include table names if the query involves multiple tables

## License
MIT

## Contributing
Contributions are welcome! Please feel free to submit a pull request.

## Acknowledgements
- [FastMCP](https://github.com/jtsang4/fastmcp) - The MCP communication framework
- [OpenRouter](https://openrouter.ai/) - AI model provider
- [FastAPI](https://fastapi.tiangolo.com/) - API framework
