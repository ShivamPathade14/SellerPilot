"""Configuration management for SellerPilot AI.
Loads settings from environment variables or .env file with sensible defaults.
"""

import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    # Load .env if present in workspace root
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


class Settings:
    """Application settings with defaults optimized for local development and testing."""

    # Claude LLM API
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Mock Mode: when True, use MockInventoryService and MockContentService
    USE_MOCKS: bool = os.getenv("USE_MOCKS", "true").lower() in ("true", "1", "yes")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sellerpilot.db")

    # API Configuration
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # Commerce Agent Escalation Threshold
    ESCALATION_CONFIDENCE_THRESHOLD: float = float(os.getenv("ESCALATION_CONFIDENCE_THRESHOLD", "0.7"))


# Global singleton instance
settings = Settings()
