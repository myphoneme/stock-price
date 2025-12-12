"""FastAPI MCP Server - Main Application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import mcp_router, chat_router, stock_router

# Print startup info
print(f"Database configured: {settings.DB_HOST}/{settings.DB_NAME}")
print(f"Base directory for files: {settings.BASE_DIR}")

# Create FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Model Context Protocol server with file operations, web tools, and user management",
    version="1.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(mcp_router)
app.include_router(chat_router)
app.include_router(stock_router)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "base_dir": str(settings.BASE_DIR),
        "database": f"{settings.DB_HOST}/{settings.DB_NAME}"
    }


@app.get("/")
def root():
    """Root endpoint with API info."""
    return {
        "name": "MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "mcp": "/mcp",
            "tools_list": "/mcp/tools",
            "chat": "/api/chat",
            "stock": "/api/stock/{symbol}",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
