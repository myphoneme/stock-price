"""MCP Protocol endpoints."""
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from ..tools import TOOLS
from ..handlers import TOOL_HANDLERS

router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.post("")
async def mcp_endpoint(request: Request):
    """
    Main MCP endpoint handling JSON-RPC style requests.
    Supports: initialize, tools/list, tools/call
    """
    try:
        body = await request.json()
    except Exception:
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
                "capabilities": {"tools": {}},
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
            "result": {"tools": TOOLS}
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
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }]
                }
            })
        except HTTPException as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": e.detail}
            })
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(e)}
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


@router.get("/tools")
def list_tools():
    """List available tools (legacy endpoint)."""
    return {"tools": TOOLS}


@router.post("/run")
async def run_tool(request: Request):
    """Run a tool (legacy endpoint)."""
    body = await request.json()
    tool = body.get("tool")
    inp = body.get("input", {})

    if tool not in TOOL_HANDLERS:
        return {"error": f"Unknown tool: {tool}"}

    result = await TOOL_HANDLERS[tool](inp)
    return result
