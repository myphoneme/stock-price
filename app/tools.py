"""MCP Tool definitions."""

# --- File Operation Tools ---
FILE_TOOLS = [
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
    }
]

# --- Web Tools ---
WEB_TOOLS = [
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
    }
]

# --- User CRUD Tools ---
USER_TOOLS = [
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

# --- All Tools Combined ---
TOOLS = FILE_TOOLS + WEB_TOOLS + USER_TOOLS
