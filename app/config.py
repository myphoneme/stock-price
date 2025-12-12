"""Application configuration settings."""
import os
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    print("python-dotenv not installed, using system environment variables")


class Settings:
    """Application settings loaded from environment variables."""

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Database Configuration
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "fastapi_db")

    # File Operations Configuration
    BASE_DIR: Path = Path(__file__).parent.parent / "mcp_files"
    MAX_FILE_BYTES: int = 100 * 1024  # 100 KB

    @property
    def db_config(self) -> dict:
        """Return database configuration dictionary."""
        return {
            "host": self.DB_HOST,
            "user": self.DB_USER,
            "password": self.DB_PASSWORD,
            "db": self.DB_NAME,
            "autocommit": True
        }


settings = Settings()

# Ensure mcp_files directory exists
settings.BASE_DIR.mkdir(parents=True, exist_ok=True)
