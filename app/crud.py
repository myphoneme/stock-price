"""CRUD operations for database entities."""
from typing import Optional, List, Dict, Any
from .database import get_db_cursor, serialize_datetime


# --- User CRUD Operations ---
async def get_all_users() -> Dict[str, Any]:
    """Get all users from the database."""
    try:
        async with get_db_cursor() as cursor:
            await cursor.execute(
                "SELECT id, name, email, role, is_active, created_at, updated_at FROM users"
            )
            users = await cursor.fetchall()
            users = [serialize_datetime(user) for user in users]
        return {"users": users, "count": len(users)}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def get_user_by_id(user_id: int) -> Dict[str, Any]:
    """Get a user by ID."""
    try:
        async with get_db_cursor() as cursor:
            await cursor.execute(
                "SELECT id, name, email, role, is_active, created_at, updated_at FROM users WHERE id = %s",
                (user_id,)
            )
            user = await cursor.fetchone()
        if not user:
            return {"error": f"User with id {user_id} not found"}
        return {"user": serialize_datetime(user)}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def create_user(name: str, email: str, password: str, role: int = 1) -> Dict[str, Any]:
    """Create a new user."""
    try:
        async with get_db_cursor(dict_cursor=False) as cursor:
            # Check if email already exists
            await cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if await cursor.fetchone():
                return {"error": f"User with email {email} already exists"}

            # Insert new user
            await cursor.execute(
                """INSERT INTO users (name, email, password, role, is_active, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, 1, NOW(), NOW())""",
                (name, email, password, role)
            )
            new_id = cursor.lastrowid
        return {"success": True, "message": "User created successfully", "id": new_id}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def update_user(user_id: int, **kwargs) -> Dict[str, Any]:
    """Update an existing user."""
    # Build update fields dynamically
    update_fields = []
    update_values = []

    for field in ['name', 'email', 'role', 'is_active']:
        if field in kwargs and kwargs[field] is not None:
            update_fields.append(f"{field} = %s")
            update_values.append(kwargs[field])

    if not update_fields:
        return {"error": "No fields to update. Provide at least one of: name, email, role, is_active"}

    update_fields.append("updated_at = NOW()")
    update_values.append(user_id)

    try:
        async with get_db_cursor(dict_cursor=False) as cursor:
            # Check if user exists
            await cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not await cursor.fetchone():
                return {"error": f"User with id {user_id} not found"}

            # Update user
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
            await cursor.execute(query, update_values)
        return {"success": True, "message": f"User {user_id} updated successfully"}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


async def delete_user(user_id: int) -> Dict[str, Any]:
    """Delete a user from the database."""
    try:
        async with get_db_cursor(dict_cursor=False) as cursor:
            # Check if user exists
            await cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not await cursor.fetchone():
                return {"error": f"User with id {user_id} not found"}

            # Delete user
            await cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        return {"success": True, "message": f"User {user_id} deleted successfully"}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
