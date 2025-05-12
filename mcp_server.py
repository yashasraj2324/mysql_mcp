#!/usr/bin/env python3
"""
MySQL MCP Server

This script provides a FastMCP server with tools for MySQL database operations.
"""

import os
import sys
import re
import logging
from mysql.connector import connect, Error
from mcp.server.fastmcp import FastMCP
from typing import Dict, List, Any, Optional
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mysql_mcp_server")

# Create an MCP server
mcp = FastMCP("MySQL_AI_Agent")

# MySQL reserved keywords that need backtick escaping
RESERVED_KEYWORDS = {
    'rank', 'group', 'order', 'table', 'index', 'key', 'primary', 'default',
    'create', 'select', 'insert', 'update', 'delete', 'where', 'from', 'join'
}

def get_db_config():
    """Get database configuration from environment variables."""
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "")
    }
    if not all([config["user"], config["password"], config["database"]]):
        logger.error("Missing required database configuration.")
        raise ValueError("Missing required database configuration")
    return config

def escape_identifier(name: str) -> str:
    """Escape identifiers that might be MySQL reserved keywords."""
    name = re.sub(r'[^\w]', '', name)
    if name.lower() in RESERVED_KEYWORDS:
        return f"`{name}`"
    return name

@mcp.tool()
def query_data(sql: str) -> str:
    """Execute SQL queries safely"""
    logger.info(f"Executing SQL query: {sql}")
    
    # Basic SQL injection prevention for non-SELECT queries
    if not sql.strip().upper().startswith("SELECT"):
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER']
        if any(keyword in sql.upper() for keyword in dangerous_keywords):
            logger.warning(f"Potentially dangerous SQL operation detected: {sql}")
            return "Error: Potentially dangerous SQL operation detected"
    
    config = get_db_config()
    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                if cursor.description is not None:
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    
                    # Format results nicely
                    header = " | ".join(columns)
                    separator = "-" * len(header)
                    result_rows = [" | ".join(str(val) if val is not None else 'NULL' for val in row) for row in rows]
                    
                    if result_rows:
                        return f"{header}\n{separator}\n" + "\n".join(result_rows)
                    else:
                        return "Query returned no results"
                else:
                    conn.commit()
                    return f"Query executed successfully. Rows affected: {cursor.rowcount}"
    except Error as e:
        logger.error(f"Error executing SQL '{sql}': {e}")
        return f"Error executing query: {str(e)}"

@mcp.tool()
def list_tables() -> str:
    """List all tables in the database."""
    config = get_db_config()
    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = [table[0] for table in cursor.fetchall()]
                if tables:
                    return "\n".join(tables)
                else:
                    return "No tables found in the database"
    except Error as e:
        logger.error(f"Error listing tables: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def describe_table(table: str) -> str:
    """Describe the structure of a table."""
    config = get_db_config()
    try:
        escaped_table = escape_identifier(table)
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"DESCRIBE {escaped_table}")
                columns = cursor.fetchall()
                if columns:
                    headers = ["Field", "Type", "Null", "Key", "Default", "Extra"]
                    header_str = " | ".join(headers)
                    separator = "-" * len(header_str)
                    rows = [" | ".join(str(val) if val is not None else 'NULL' for val in row) for row in columns]
                    return f"{header_str}\n{separator}\n" + "\n".join(rows)
                else:
                    return f"No columns found for table {table}"
    except Error as e:
        logger.error(f"Error describing table {table}: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def get_database_schema() -> str:
    """Get the complete schema of the database with tables and their columns."""
    config = get_db_config()
    try:
        schema_info = []
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                # Get list of tables
                cursor.execute("SHOW TABLES")
                tables = [table[0] for table in cursor.fetchall()]
                
                for table in tables:
                    schema_info.append(f"\nTABLE: {table}")
                    cursor.execute(f"DESCRIBE {table}")
                    columns = cursor.fetchall()
                    
                    column_info = []
                    for col in columns:
                        field, type_, null, key, default, extra = col
                        column_info.append(f"  - {field} ({type_}){' PRIMARY KEY' if key == 'PRI' else ''}")
                    
                    schema_info.extend(column_info)
        
        if schema_info:
            return "\n".join(schema_info)
        else:
            return "No tables found in the database"
    except Error as e:
        logger.error(f"Error getting database schema: {e}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    print("Starting MySQL MCP server...", file=sys.stderr)
    try:
        config = get_db_config()
        print(f"Connected to MySQL at {config['host']}:{config['port']}", file=sys.stderr)
        print(f"Database: {config['database']}", file=sys.stderr)
        logger.info("Server ready to process requests")
        # Initialize and run the server
        mcp.run(transport="stdio")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
