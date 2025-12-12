"""MCP Tool handler implementations."""
from typing import Dict, Any
from pathlib import Path
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from .config import settings
from . import crud


# --- Utilities ---
def safe_resolve(requested_path: str) -> Path:
    """Resolve path safely within BASE_DIR."""
    rp = Path(requested_path)
    if rp.is_absolute():
        rp = rp.relative_to(rp.anchor) if rp.anchor else rp
    resolved = (settings.BASE_DIR / rp).resolve()
    base_resolved = settings.BASE_DIR.resolve()
    if not str(resolved).startswith(str(base_resolved)):
        raise HTTPException(status_code=403, detail="Access denied (outside allowed folder).")
    return resolved


# --- File Operation Handlers ---
async def handle_list_directory(args: Dict[str, Any]) -> Dict[str, Any]:
    """List files and folders in a directory."""
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


async def handle_read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Read the contents of a text file."""
    path = args.get("path")
    if not path:
        return {"error": "Missing 'path' parameter"}
    p = safe_resolve(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}
    if not p.is_file():
        return {"error": f"Not a file: {path}"}
    size = p.stat().st_size
    if size > settings.MAX_FILE_BYTES:
        return {"error": f"File too large ({size} bytes). Max: {settings.MAX_FILE_BYTES} bytes"}
    try:
        content = p.read_text(encoding="utf-8")
        return {"path": path, "content": content, "size": size}
    except UnicodeDecodeError:
        return {"error": f"File is not readable as UTF-8 text: {path}"}


async def handle_write_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Write content to a file."""
    path = args.get("path")
    content = args.get("content")
    if not path:
        return {"error": "Missing 'path' parameter"}
    if content is None:
        return {"error": "Missing 'content' parameter"}
    p = safe_resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"success": True, "path": path, "size": len(content)}


async def handle_create_directory(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new directory."""
    path = args.get("path")
    if not path:
        return {"error": "Missing 'path' parameter"}
    p = safe_resolve(path)
    p.mkdir(parents=True, exist_ok=True)
    return {"success": True, "path": path}


async def handle_delete_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a file."""
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


# --- Web Handlers ---
async def handle_fetch_url(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch content from a URL."""
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
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()
                text = soup.get_text(separator="\n", strip=True)
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                content = "\n".join(lines)
            return {
                "url": str(response.url),
                "status_code": response.status_code,
                "content": content[:50000]
            }
    except httpx.HTTPError as e:
        return {"error": f"HTTP error: {str(e)}"}
    except Exception as e:
        return {"error": f"Error fetching URL: {str(e)}"}


async def handle_crawl_links(args: Dict[str, Any]) -> Dict[str, Any]:
    """Crawl a webpage and extract all links."""
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
                if href.startswith("/"):
                    href = urljoin(url, href)
                if filter_domain and filter_domain not in href:
                    continue
                if href.startswith("http"):
                    links.append({"url": href, "text": text[:100]})
            return {"url": url, "links": links[:100]}
    except Exception as e:
        return {"error": f"Error crawling URL: {str(e)}"}


async def handle_search_web(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search the web using DuckDuckGo."""
    query = args.get("query")
    max_results = args.get("max_results", 5)
    if not query:
        return {"error": "Missing 'query' parameter"}
    try:
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
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    link = ""
                    a_tag = result.select_one("a.result__a")
                    if a_tag and a_tag.get("href"):
                        link = a_tag["href"]
                    results.append({"title": title, "snippet": snippet, "url": link})
            return {"query": query, "results": results}
    except Exception as e:
        return {"error": f"Error searching: {str(e)}"}


async def handle_get_stock_price(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get live stock price."""
    symbol = args.get("symbol")
    if not symbol:
        return {"error": "Missing 'symbol' parameter"}

    symbol = symbol.upper().strip()

    # Detect market from symbol suffix
    if symbol.endswith(".NS"):
        market, currency = "NSE", "INR"
    elif symbol.endswith(".BO"):
        market, currency = "BSE", "INR"
    else:
        market, currency = "US", "USD"

    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            data = response.json()

            result = data.get("chart", {}).get("result", [])
            if not result:
                return {"error": f"No data found for symbol: {symbol}"}

            meta = result[0].get("meta", {})
            current_price = meta.get("regularMarketPrice", 0)
            previous_close = meta.get("previousClose", meta.get("chartPreviousClose", 0))
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


# --- User CRUD Handlers ---
async def handle_get_all_users(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get all users."""
    return await crud.get_all_users()


async def handle_get_user_by_id(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get a user by ID."""
    user_id = args.get("id")
    if not user_id:
        return {"error": "Missing 'id' parameter"}
    return await crud.get_user_by_id(user_id)


async def handle_create_user(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new user."""
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

    return await crud.create_user(name, email, password, role)


async def handle_update_user(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing user."""
    user_id = args.get("id")
    if not user_id:
        return {"error": "Missing 'id' parameter"}
    return await crud.update_user(
        user_id,
        name=args.get("name"),
        email=args.get("email"),
        role=args.get("role"),
        is_active=args.get("is_active")
    )


async def handle_delete_user(args: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a user."""
    user_id = args.get("id")
    if not user_id:
        return {"error": "Missing 'id' parameter"}
    return await crud.delete_user(user_id)


# --- Tool Dispatcher ---
TOOL_HANDLERS = {
    # File tools
    "list_directory": handle_list_directory,
    "read_file": handle_read_file,
    "write_file": handle_write_file,
    "create_directory": handle_create_directory,
    "delete_file": handle_delete_file,
    # Web tools
    "fetch_url": handle_fetch_url,
    "crawl_links": handle_crawl_links,
    "search_web": handle_search_web,
    "get_stock_price": handle_get_stock_price,
    # User CRUD tools
    "get_all_users": handle_get_all_users,
    "get_user_by_id": handle_get_user_by_id,
    "create_user": handle_create_user,
    "update_user": handle_update_user,
    "delete_user": handle_delete_user,
}

# Chat-specific tool handlers (subset for chatbot)
CHAT_TOOL_HANDLERS = {
    "get_all_users": handle_get_all_users,
    "get_user_by_id": handle_get_user_by_id,
    "create_user": handle_create_user,
    "update_user": handle_update_user,
    "delete_user": handle_delete_user,
}
