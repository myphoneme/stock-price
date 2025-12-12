"""Database connection and utilities."""
import aiomysql
from contextlib import asynccontextmanager
from .config import settings


async def get_db_connection():
    """Create a database connection."""
    return await aiomysql.connect(**settings.db_config)


@asynccontextmanager
async def get_db_cursor(dict_cursor: bool = True):
    """
    Async context manager for database operations.

    Usage:
        async with get_db_cursor() as cursor:
            await cursor.execute("SELECT * FROM users")
            result = await cursor.fetchall()
    """
    conn = await get_db_connection()
    try:
        cursor_class = aiomysql.DictCursor if dict_cursor else aiomysql.Cursor
        async with conn.cursor(cursor_class) as cursor:
            yield cursor
    finally:
        conn.close()


def serialize_datetime(record: dict) -> dict:
    """Convert datetime objects to strings in a record."""
    if record:
        for key in ['created_at', 'updated_at']:
            if key in record and record[key]:
                record[key] = str(record[key])
    return record
