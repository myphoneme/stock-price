"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr
from typing import Optional, Any, Dict, List


# --- User Schemas ---
class UserBase(BaseModel):
    name: str
    email: str


class UserCreate(UserBase):
    password: str
    role: int = 1


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[int] = None
    is_active: Optional[int] = None


class UserResponse(UserBase):
    id: int
    role: int
    is_active: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UsersListResponse(BaseModel):
    users: List[dict]
    count: int


# --- MCP Protocol Schemas ---
class ToolInput(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = {}
    required: List[str] = []


class Tool(BaseModel):
    name: str
    description: str
    inputSchema: ToolInput


class MCPRequest(BaseModel):
    method: str
    params: Dict[str, Any] = {}
    id: Optional[Any] = None


class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


# --- Chat Schemas ---
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    tool_used: Optional[str] = None
    raw_result: Optional[Dict[str, Any]] = None


# --- Tool Request Schemas ---
class ToolRunRequest(BaseModel):
    tool: str
    input: Dict[str, Any] = {}
