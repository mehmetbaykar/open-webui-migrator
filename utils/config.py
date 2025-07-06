"""Configuration module for OpenWebUI migrator."""

import os
from pathlib import Path
from typing import Dict, List, Any


class Config:
    """Centralized configuration for the migrator."""

    # Container configuration
    CONTAINER_NAME: str = "open-webui"
    CONTAINER_DB_PATH: str = "/app/backend/data/webui.db"
    CONTAINER_UPLOADS_PATH: str = "/app/backend/data/uploads"

    # Local paths
    LOCAL_DB_NAME: str = "webui.db"
    LOCAL_DB_BACKUP_NAME: str = "webui.db.backup"
    CONVERSATIONS_SQL_NAME: str = "conversations.sql"
    MEMORY_SQL_NAME: str = "memory.sql"

    # Directory names
    DATA_DIR: str = "data"
    OUTPUT_DIR: str = "output"

    # Provider configuration
    SUPPORTED_PROVIDERS: Dict[str, Dict[str, Any]] = {
        "chatgpt": {
            "name": "ChatGPT",
            "required_files": ["conversations.json"],
            "optional_files": ["memory.txt"],
            "description": "Export from ChatGPT settings",
        }
    }

    # File patterns
    JSON_EXTENSION: str = ".json"

    # Environment variables
    USER_ID_ENV_VAR: str = "USER_ID"

    @classmethod
    def get_provider_path(cls, provider: str) -> Path:
        """Get the data path for a specific provider."""
        return Path(cls.DATA_DIR) / provider

    @classmethod
    def get_output_path(cls, provider: str) -> Path:
        """Get the output path for a specific provider."""
        return Path(cls.OUTPUT_DIR) / provider

    @classmethod
    def get_env_user_id(cls) -> str:
        """Get user ID from environment variable."""
        return os.getenv(cls.USER_ID_ENV_VAR, "")

    @classmethod
    def get_artifacts_to_clean(cls) -> List[str]:
        """Get list of artifacts to clean after migration."""
        return [
            cls.OUTPUT_DIR,
            cls.LOCAL_DB_NAME,
            cls.CONVERSATIONS_SQL_NAME,
            cls.MEMORY_SQL_NAME,
        ]
