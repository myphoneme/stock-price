# server.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from pathlib import Path
import json
import httpx
from bs4 import BeautifulSoup
import asyncio
import aiomysql
import os
import re

# Load environment variables (dotenv is optional)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    print("python-dotenv not installed, using system environment variables")

# --- OpenAI Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None

if OPENAI_API_KEY and OPENAI_API_KEY != "sk-your-api-key-here":
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print(f"OpenAI client initialized successfully")
    except Exception as e:
        print(f"Failed to initialize OpenAI client: {e}")
else:
    print("WARNING: OpenAI API key not configured. Chat endpoint will not work.")

# --- MySQL Database Configuration (from environment variables) ---
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "db": os.getenv("DB_NAME", "fastapi_db"),
    "autocommit": True
}
print(f"Database configured: {DB_CONFIG['host']}/{DB_CONFIG['db']}")

app = FastAPI(title="MCP Server")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIG ---
# Base directory for file operations (relative to project root)
BASE_DIR = Path(__file__).parent.parent / "mcp_files"
BASE_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_BYTES = 100 * 1024  # 100 KB max read for safety

# --- MCP Protocol Models ---
class ToolInput(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = {}
    required: List[str] = []

class Tool(BaseModel):
    name: str
    description: str
    inputSchema: ToolInput

class CallToolRequest(BaseModel):
    method: str = "tools/call"
    params: Dict[str, Any]

# --- Utilities ---
def safe_resolve(requested_path: str) -> Path:
    """Resolve path safely within BASE_DIR"""
    rp = Path(requested_path)
    if rp.is_absolute():
        rp = rp.relative_to(rp.anchor) if rp.anchor else rp
    resolved = (BASE_DIR / rp).resolve()
    base_resolved = BASE_DIR.resolve()
    if not str(resolved).startswith(str(base_resolved)):
        raise HTTPException(status_code=403, detail="Access denied (outside allowed folder).")
    return resolved

# --- Tool Definitions ---
TOOLS = [
    {
        "name": "list_directory",
        "description": "List files and folders in a directory. Path is relative to the server's base folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to base folder. Use '.' for root."
                }
            },
            "required": []
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a text file. Path is relative to server's base folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to base folder"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to base folder"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "create_directory",
        "description": "Create a new directory. Path is relative to server's base folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to create"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "delete_file",
        "description": "Delete a file. Path is relative to server's base folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to delete"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "fetch_url",
        "description": "Fetch content from a URL and return it as text. Useful for web surfing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch"
                },
                "extract_text": {
                    "type": "boolean",
                    "description": "If true, extract only text content from HTML (default: true)"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "crawl_links",
        "description": "Crawl a webpage and extract all links from it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to crawl for links"
                },
                "filter_domain": {
                    "type": "string",
                    "description": "Optional: only return links from this domain"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "search_web",
        "description": "Search the web using DuckDuckGo and return results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 5)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_stock_price",
        "description": "Get live stock price for US (NYSE/NASDAQ) or Indian (NSE/BSE) markets. Use .NS suffix for NSE, .BO for BSE, no suffix for US stocks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'AAPL' for Apple, 'RELIANCE.NS' for Reliance on NSE, 'TCS.BO' for TCS on BSE)"
                }
            },
            "required": ["symbol"]
        }
    },
    # --- User CRUD Tools ---
    {
        "name": "get_all_users",
        "description": "Get all users from the database. Returns a list of all users with their details.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_user_by_id",
        "description": "Get a specific user by their ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "The user ID to retrieve"
                }
            },
            "required": ["id"]
        }
    },
    {
        "name": "create_user",
        "description": "Create a new user in the database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Full name of the user"
                },
                "email": {
                    "type": "string",
                    "description": "Email address of the user"
                },
                "password": {
                    "type": "string",
                    "description": "Password for the user (will be stored as provided)"
                },
                "role": {
                    "type": "integer",
                    "description": "Role ID of the user (default: 1)"
                }
            },
            "required": ["name", "email", "password"]
        }
    },
    {
        "name": "update_user",
        "description": "Update an existing user's information.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "The user ID to update"
                },
                "name": {
                    "type": "string",
                    "description": "New name for the user (optional)"
                },
                "email": {
                    "type": "string",
                    "description": "New email for the user (optional)"
                },
                "role": {
                    "type": "integer",
                    "description": "New role ID for the user (optional)"
                },
                "is_active": {
                    "type": "integer",
                    "description": "Set user active status (0 or 1, optional)"
                }
            },
            "required": ["id"]
        }
    },
    {
        "name": "delete_user",
        "description": "Delete a user from the database by their ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "The user ID to delete"
                }
            },
            "required": ["id"]
        }
    }
]

# --- Tool Implementations ---
async def tool_list_directory(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path", ".")
    p = safe_resolve(path)
    if not p.exists():
        return {"error": f"Path does not exist: {path}"}
    if not p.is_dir():
        return {"error": f"Path is not a directory: {path}"}
    entries = []
    for child in sorted(p.iterdir()):
        entries.append({
            "name": child.name,
            "type": "directory" if child.is_dir() else "file",
            "size": child.stat().st_size if child.is_file() else None
        })
    return {"path": path, "entries": entries}

async def tool_read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    if not path:
        return {"error": "Missing 'path' parameter"}
    p = safe_resolve(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}
    if not p.is_file():
        return {"error": f"Not a file: {path}"}
    size = p.stat().st_size
    if size > MAX_FILE_BYTES:
        return {"error": f"File too large ({size} bytes). Max: {MAX_FILE_BYTES} bytes"}
    try:
        content = p.read_text(encoding="utf-8")
        return {"path": path, "content": content, "size": size}
    except UnicodeDecodeError:
        return {"error": f"File is not readable as UTF-8 text: {path}"}

async def tool_write_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    content = args.get("content")
    if not path:
        return {"error": "Missing 'path' parameter"}
    if content is None:
        return {"error": "Missing 'content' parameter"}
    p = safe_resolve(path)
    # Create parent directories if needed
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"success": True, "path": path, "size": len(content)}

async def tool_create_directory(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    if not path:
        return {"error": "Missing 'path' parameter"}
    p = safe_resolve(path)
    p.mkdir(parents=True, exist_ok=True)
    return {"success": True, "path": path}

async def tool_delete_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    if not path:
        return {"error": "Missing 'path' parameter"}
    p = safe_resolve(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}
    if not p.is_file():
        return {"error": f"Not a file: {path}"}
    p.unlink()
    return {"success": True, "path": path}

async def tool_fetch_url(args: Dict[str, Any]) -> Dict[str, Any]:
    url = args.get("url")
    extract_text = args.get("extract_text", True)
    if not url:
        return {"error": "Missing 'url' parameter"}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            content = response.text
            if extract_text and "text/html" in response.headers.get("content-type", ""):
                soup = BeautifulSoup(content, "html.parser")
                # Remove script and style elements
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()
                text = soup.get_text(separator="\n", strip=True)
                # Clean up multiple newlines
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                content = "\n".join(lines)
            return {
                "url": str(response.url),
                "status_code": response.status_code,
                "content": content[:50000]  # Limit content size
            }
    except httpx.HTTPError as e:
        return {"error": f"HTTP error: {str(e)}"}
    except Exception as e:
        return {"error": f"Error fetching URL: {str(e)}"}

async def tool_crawl_links(args: Dict[str, Any]) -> Dict[str, Any]:
    url = args.get("url")
    filter_domain = args.get("filter_domain")
    if not url:
        return {"error": "Missing 'url' parameter"}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            links = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                text = a_tag.get_text(strip=True)
                # Convert relative URLs to absolute
                if href.startswith("/"):
                    from urllib.parse import urljoin
                    href = urljoin(url, href)
                if filter_domain and filter_domain not in href:
                    continue
                if href.startswith("http"):
                    links.append({"url": href, "text": text[:100]})
            return {"url": url, "links": links[:100]}  # Limit to 100 links
    except Exception as e:
        return {"error": f"Error crawling URL: {str(e)}"}

async def tool_search_web(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query")
    max_results = args.get("max_results", 5)
    if not query:
        return {"error": "Missing 'query' parameter"}
    try:
        # Use DuckDuckGo HTML search
        search_url = f"https://html.duckduckgo.com/html/?q={query}"
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            for result in soup.select(".result")[:max_results]:
                title_elem = result.select_one(".result__title")
                snippet_elem = result.select_one(".result__snippet")
                link_elem = result.select_one(".result__url")
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    link = ""
                    if link_elem:
                        link = link_elem.get_text(strip=True)
                    # Try to get actual URL from href
                    a_tag = result.select_one("a.result__a")
                    if a_tag and a_tag.get("href"):
                        link = a_tag["href"]
                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": link
                    })
            return {"query": query, "results": results}
    except Exception as e:
        return {"error": f"Error searching: {str(e)}"}

async def tool_get_stock_price(args: Dict[str, Any]) -> Dict[str, Any]:
    symbol = args.get("symbol")
    if not symbol:
        return {"error": "Missing 'symbol' parameter"}

    symbol = symbol.upper().strip()

    # Detect market from symbol suffix
    if symbol.endswith(".NS"):
        market = "NSE"
        currency = "INR"
    elif symbol.endswith(".BO"):
        market = "BSE"
        currency = "INR"
    else:
        market = "US"
        currency = "USD"

    try:
        # Yahoo Finance API
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            data = response.json()

            # Parse response
            result = data.get("chart", {}).get("result", [])
            if not result:
                return {"error": f"No data found for symbol: {symbol}"}

            quote = result[0]
            meta = quote.get("meta", {})

            # Get current price and other details
            current_price = meta.get("regularMarketPrice", 0)
            previous_close = meta.get("previousClose", meta.get("chartPreviousClose", 0))

            # Calculate change
            change = round(current_price - previous_close, 2) if previous_close else 0
            change_percent = round((change / previous_close) * 100, 2) if previous_close else 0

            return {
                "symbol": symbol,
                "name": meta.get("shortName", meta.get("symbol", symbol)),
                "market": market,
                "currency": meta.get("currency", currency),
                "price": current_price,
                "change": change,
                "change_percent": change_percent,
                "day_high": meta.get("regularMarketDayHigh", meta.get("dayHigh", "N/A")),
                "day_low": meta.get("regularMarketDayLow", meta.get("dayLow", "N/A")),
                "volume": meta.get("regularMarketVolume", "N/A"),
                "market_state": meta.get("marketState", "UNKNOWN"),
                "exchange": meta.get("exchangeName", market),
                "timestamp": meta.get("regularMarketTime", "N/A")
            }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"error": f"Symbol not found: {symbol}. For Indian stocks, use .NS (NSE) or .BO (BSE) suffix."}
        return {"error": f"HTTP error: {str(e)}"}
    except Exception as e:
        return {"error": f"Error fetching stock price: {str(e)}"}

# --- User CRUD Tool Implementations ---
async def get_db_connection():
    """Create a database connection"""
    return await aiomysql.connect(**DB_CONFIG)

async def tool_get_all_users(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get all users from the database"""
    try:
        conn = await get_db_connection()
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT id, name, email, role, is_active, created_at, updated_at FROM users")
            users = await cursor.fetchall()
            # Convert datetime objects to strings
            for user in users:
                if user.get('created_at'):
                    user['created_at'] = str(user['created_at'])
                if user.get('updated_at'):
                    user['updated_at'] = str(user['updated_at'])
        conn.close()
        return {"users": users, "count": len(users)}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

async def tool_get_user_by_id(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get a user by ID"""
    user_id = args.get("id")
    if not user_id:
        return {"error": "Missing 'id' parameter"}
    try:
        conn = await get_db_connection()
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                "SELECT id, name, email, role, is_active, created_at, updated_at FROM users WHERE id = %s",
                (user_id,)
            )
            user = await cursor.fetchone()
        conn.close()
        if not user:
            return {"error": f"User with id {user_id} not found"}
        # Convert datetime objects to strings
        if user.get('created_at'):
            user['created_at'] = str(user['created_at'])
        if user.get('updated_at'):
            user['updated_at'] = str(user['updated_at'])
        return {"user": user}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

async def tool_create_user(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new user"""
    name = args.get("name")
    email = args.get("email")
    password = args.get("password")
    role = args.get("role", 1)

    if not name:
        return {"error": "Missing 'name' parameter"}
    if not email:
        return {"error": "Missing 'email' parameter"}
    if not password:
        return {"error": "Missing 'password' parameter"}

    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            # Check if email already exists
            await cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing = await cursor.fetchone()
            if existing:
                conn.close()
                return {"error": f"User with email {email} already exists"}

            # Insert new user
            await cursor.execute(
                """INSERT INTO users (name, email, password, role, is_active, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, 1, NOW(), NOW())""",
                (name, email, password, role)
            )
            new_id = cursor.lastrowid
        conn.close()
        return {"success": True, "message": "User created successfully", "id": new_id}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

async def tool_update_user(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing user"""
    user_id = args.get("id")
    if not user_id:
        return {"error": "Missing 'id' parameter"}

    # Build update fields dynamically
    update_fields = []
    update_values = []

    if "name" in args and args["name"]:
        update_fields.append("name = %s")
        update_values.append(args["name"])
    if "email" in args and args["email"]:
        update_fields.append("email = %s")
        update_values.append(args["email"])
    if "role" in args:
        update_fields.append("role = %s")
        update_values.append(args["role"])
    if "is_active" in args:
        update_fields.append("is_active = %s")
        update_values.append(args["is_active"])

    if not update_fields:
        return {"error": "No fields to update. Provide at least one of: name, email, role, is_active"}

    update_fields.append("updated_at = NOW()")
    update_values.append(user_id)

    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            # Check if user exists
            await cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            existing = await cursor.fetchone()
            if not existing:
                conn.close()
                return {"error": f"User with id {user_id} not found"}

            # Update user
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
            await cursor.execute(query, update_values)
        conn.close()
        return {"success": True, "message": f"User {user_id} updated successfully"}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

async def tool_delete_user_db(args: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a user from the database"""
    user_id = args.get("id")
    if not user_id:
        return {"error": "Missing 'id' parameter"}

    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            # Check if user exists
            await cursor.execute("SELECT id, name FROM users WHERE id = %s", (user_id,))
            existing = await cursor.fetchone()
            if not existing:
                conn.close()
                return {"error": f"User with id {user_id} not found"}

            # Delete user
            await cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.close()
        return {"success": True, "message": f"User {user_id} deleted successfully"}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

# Tool dispatcher
TOOL_HANDLERS = {
    "list_directory": tool_list_directory,
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "create_directory": tool_create_directory,
    "delete_file": tool_delete_file,
    "fetch_url": tool_fetch_url,
    "crawl_links": tool_crawl_links,
    "search_web": tool_search_web,
    "get_stock_price": tool_get_stock_price,
    # User CRUD tools
    "get_all_users": tool_get_all_users,
    "get_user_by_id": tool_get_user_by_id,
    "create_user": tool_create_user,
    "update_user": tool_update_user,
    "delete_user": tool_delete_user_db,
}

# --- MCP HTTP Endpoints (Streamable HTTP Transport) ---

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Main MCP endpoint handling JSON-RPC style requests.
    Supports: initialize, tools/list, tools/call
    """
    try:
        body = await request.json()
    except:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")

    # Handle initialize
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "mcp-file-web-server",
                    "version": "1.0.0"
                }
            }
        })

    # Handle tools/list
    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": TOOLS
            }
        })

    # Handle tools/call
    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name not in TOOL_HANDLERS:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            })

        try:
            result = await TOOL_HANDLERS[tool_name](tool_args)
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            })
        except HTTPException as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": e.detail
                }
            })
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": str(e)
                }
            })

    # Unknown method
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}"
        }
    })

# --- Legacy endpoints (keep for backward compatibility) ---
@app.get("/mcp/tools")
def list_tools():
    """List available tools (legacy endpoint)"""
    return {"tools": TOOLS}

@app.post("/mcp/run")
async def run_tool(request: Request):
    """Run a tool (legacy endpoint)"""
    body = await request.json()
    tool = body.get("tool")
    inp = body.get("input", {})

    if tool not in TOOL_HANDLERS:
        return {"error": f"Unknown tool: {tool}"}

    result = await TOOL_HANDLERS[tool](inp)
    return result

# --- Health check ---
@app.get("/health")
def health():
    return {"status": "ok", "base_dir": str(BASE_DIR)}

# --- REST API for React frontend ---
@app.get("/api/stock/{symbol}")
async def get_stock_api(symbol: str):
    """Simple REST endpoint for stock price - used by React frontend"""
    result = await tool_get_stock_price({"symbol": symbol})
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# --- Chatbot API Endpoint ---
CHAT_SYSTEM_PROMPT = """You are a helpful assistant that can interact with a database of users.

You have access to the following tools to manage users:
1. get_all_users - Get all users from the database
2. get_user_by_id - Get a specific user by their ID (requires: id)
3. create_user - Create a new user (requires: name, email, password; optional: role)
4. update_user - Update an existing user (requires: id; optional: name, email, role, is_active)
5. delete_user - Delete a user by ID (requires: id)

When the user asks about users or wants to perform database operations, respond with a JSON object in this exact format:
{"tool": "tool_name", "arguments": {"arg1": "value1", "arg2": "value2"}}

Examples:
- "Show all users" -> {"tool": "get_all_users", "arguments": {}}
- "Get user with ID 1" -> {"tool": "get_user_by_id", "arguments": {"id": 1}}
- "Add user John with email john@test.com and password 123456" -> {"tool": "create_user", "arguments": {"name": "John", "email": "john@test.com", "password": "123456"}}
- "Update user 1 name to Jane" -> {"tool": "update_user", "arguments": {"id": 1, "name": "Jane"}}
- "Delete user 2" -> {"tool": "delete_user", "arguments": {"id": 2}}

If the user asks a general question or something not related to user management, respond naturally without JSON.
Always be helpful and concise in your responses."""

# User CRUD tool handlers for chat
CHAT_TOOL_HANDLERS = {
    "get_all_users": tool_get_all_users,
    "get_user_by_id": tool_get_user_by_id,
    "create_user": tool_create_user,
    "update_user": tool_update_user,
    "delete_user": tool_delete_user_db,
}

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Chatbot endpoint that uses OpenAI to interpret user queries and execute MCP tools"""
    try:
        body = await request.json()
        user_message = body.get("message", "")
        print(f"[CHAT] Received message: {user_message}")

        if not user_message:
            return {"response": "Please provide a message.", "tool_used": None}

        # Check if OpenAI is configured
        if openai_client is None:
            return {
                "response": "OpenAI API is not configured. Please add your API key to the .env file:\nOPENAI_API_KEY=sk-your-actual-key",
                "tool_used": None
            }

        # Call OpenAI API
        try:
            print(f"[CHAT] Calling OpenAI API...")
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=500
            )

            llm_response = response.choices[0].message.content.strip()
            print(f"[CHAT] OpenAI response: {llm_response[:100]}...")

        except Exception as e:
            print(f"[CHAT] OpenAI error: {str(e)}")
            return {"response": f"Error connecting to OpenAI: {str(e)}", "tool_used": None}

        # Try to parse as JSON tool call
        tool_result = None
        tool_used = None

        # Check if response contains a JSON tool call
        try:
            # Try to parse the entire response as JSON first
            tool_call = None

            # Method 1: Try parsing the whole response as JSON
            try:
                tool_call = json.loads(llm_response)
            except json.JSONDecodeError:
                pass

            # Method 2: Try to find JSON object with "tool" key using regex
            if not tool_call:
                # Match JSON object that contains "tool" - handles nested braces
                json_match = re.search(r'\{[^{}]*"tool"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}', llm_response)
                if json_match:
                    try:
                        tool_call = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass

            # Method 3: Find any JSON-like structure and try to parse
            if not tool_call:
                start_idx = llm_response.find('{')
                end_idx = llm_response.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    try:
                        tool_call = json.loads(llm_response[start_idx:end_idx+1])
                    except json.JSONDecodeError:
                        pass

            if tool_call and "tool" in tool_call:
                tool_name = tool_call.get("tool")
                tool_args = tool_call.get("arguments", {})
                print(f"[CHAT] Detected tool call: {tool_name} with args: {tool_args}")

                if tool_name in CHAT_TOOL_HANDLERS:
                    tool_used = tool_name
                    tool_result = await CHAT_TOOL_HANDLERS[tool_name](tool_args)

                    # Format the response based on the tool and result
                    if "error" in tool_result:
                        formatted_response = f"Error: {tool_result['error']}"
                    elif tool_name == "get_all_users":
                        users = tool_result.get("users", [])
                        if users:
                            user_list = "\n".join([f"  {i+1}. {u['name']} ({u['email']}) - ID: {u['id']}, Active: {'Yes' if u['is_active'] else 'No'}"
                                                   for i, u in enumerate(users)])
                            formatted_response = f"Found {len(users)} user(s):\n{user_list}"
                        else:
                            formatted_response = "No users found in the database."
                    elif tool_name == "get_user_by_id":
                        user = tool_result.get("user", {})
                        formatted_response = f"User Details:\n  ID: {user.get('id')}\n  Name: {user.get('name')}\n  Email: {user.get('email')}\n  Role: {user.get('role')}\n  Active: {'Yes' if user.get('is_active') else 'No'}\n  Created: {user.get('created_at')}"
                    elif tool_name == "create_user":
                        formatted_response = f"User created successfully with ID: {tool_result.get('id')}"
                    elif tool_name == "update_user":
                        formatted_response = tool_result.get("message", "User updated successfully")
                    elif tool_name == "delete_user":
                        formatted_response = tool_result.get("message", "User deleted successfully")
                    else:
                        formatted_response = json.dumps(tool_result, indent=2)

                    return {
                        "response": formatted_response,
                        "tool_used": tool_used,
                        "raw_result": tool_result
                    }
        except Exception as parse_error:
            print(f"[CHAT] Error parsing tool call: {str(parse_error)}")
            pass  # Not a valid JSON, treat as regular response

        # Return the LLM response as-is if no tool was called
        print(f"[CHAT] No tool executed, returning LLM response")
        return {
            "response": llm_response,
            "tool_used": None
        }

    except Exception as e:
        print(f"[CHAT] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"response": f"Error processing request: {str(e)}", "tool_used": None}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
