"""Chat endpoint with OpenAI integration."""
import json
import re
from fastapi import APIRouter, Request

from ..config import settings
from ..handlers import CHAT_TOOL_HANDLERS

router = APIRouter(prefix="/api", tags=["Chat"])

# Initialize OpenAI client
openai_client = None
if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "sk-your-api-key-here":
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        print("OpenAI client initialized successfully")
    except Exception as e:
        print(f"Failed to initialize OpenAI client: {e}")
else:
    print("WARNING: OpenAI API key not configured. Chat endpoint will not work.")


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


def parse_tool_call(llm_response: str) -> dict | None:
    """Parse tool call from LLM response."""
    # Method 1: Try parsing the whole response as JSON
    try:
        tool_call = json.loads(llm_response)
        if "tool" in tool_call:
            return tool_call
    except json.JSONDecodeError:
        pass

    # Method 2: Try to find JSON object with "tool" key using regex
    json_match = re.search(
        r'\{[^{}]*"tool"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}',
        llm_response
    )
    if json_match:
        try:
            tool_call = json.loads(json_match.group())
            if "tool" in tool_call:
                return tool_call
        except json.JSONDecodeError:
            pass

    # Method 3: Find any JSON-like structure and try to parse
    start_idx = llm_response.find('{')
    end_idx = llm_response.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        try:
            tool_call = json.loads(llm_response[start_idx:end_idx + 1])
            if "tool" in tool_call:
                return tool_call
        except json.JSONDecodeError:
            pass

    return None


def format_tool_result(tool_name: str, result: dict) -> str:
    """Format tool result for user-friendly display."""
    if "error" in result:
        return f"Error: {result['error']}"

    if tool_name == "get_all_users":
        users = result.get("users", [])
        if users:
            user_list = "\n".join([
                f"  {i+1}. {u['name']} ({u['email']}) - ID: {u['id']}, Active: {'Yes' if u['is_active'] else 'No'}"
                for i, u in enumerate(users)
            ])
            return f"Found {len(users)} user(s):\n{user_list}"
        return "No users found in the database."

    if tool_name == "get_user_by_id":
        user = result.get("user", {})
        return (
            f"User Details:\n"
            f"  ID: {user.get('id')}\n"
            f"  Name: {user.get('name')}\n"
            f"  Email: {user.get('email')}\n"
            f"  Role: {user.get('role')}\n"
            f"  Active: {'Yes' if user.get('is_active') else 'No'}\n"
            f"  Created: {user.get('created_at')}"
        )

    if tool_name == "create_user":
        return f"User created successfully with ID: {result.get('id')}"

    if tool_name == "update_user":
        return result.get("message", "User updated successfully")

    if tool_name == "delete_user":
        return result.get("message", "User deleted successfully")

    return json.dumps(result, indent=2)


@router.post("/chat")
async def chat_endpoint(request: Request):
    """Chatbot endpoint that uses OpenAI to interpret user queries and execute MCP tools."""
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
            print("[CHAT] Calling OpenAI API...")
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
        try:
            tool_call = parse_tool_call(llm_response)

            if tool_call:
                tool_name = tool_call.get("tool")
                tool_args = tool_call.get("arguments", {})
                print(f"[CHAT] Detected tool call: {tool_name} with args: {tool_args}")

                if tool_name in CHAT_TOOL_HANDLERS:
                    tool_result = await CHAT_TOOL_HANDLERS[tool_name](tool_args)
                    formatted_response = format_tool_result(tool_name, tool_result)

                    return {
                        "response": formatted_response,
                        "tool_used": tool_name,
                        "raw_result": tool_result
                    }
        except Exception as parse_error:
            print(f"[CHAT] Error parsing tool call: {str(parse_error)}")

        # Return the LLM response as-is if no tool was called
        print("[CHAT] No tool executed, returning LLM response")
        return {"response": llm_response, "tool_used": None}

    except Exception as e:
        print(f"[CHAT] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"response": f"Error processing request: {str(e)}", "tool_used": None}
