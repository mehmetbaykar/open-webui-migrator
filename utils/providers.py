"""Provider interface and implementations for different chat platforms."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any
import subprocess
from utils.config import Config
from utils.file_ops import SQLFileManager
from utils.exceptions import ProviderError, UnsupportedProviderError, FileOperationError
from utils.chatgpt.migrate_chatgpt_conversations import convert_file
from utils.chatgpt import parse_memory_file, create_memory_sql


class MigrationProvider(ABC):
    """Abstract base class for migration providers."""

    def __init__(self, provider_name: str):
        """Initialize the provider."""
        self.name = provider_name
        self.data_path = Config.get_provider_path(provider_name)
        self.output_path = Config.get_output_path(provider_name)

    @abstractmethod
    def validate_data_files(self) -> bool:
        """Validate that required data files exist."""

    @abstractmethod
    def convert_conversations(self, user_id: str) -> None:
        """Convert conversations to OpenWebUI format."""

    @abstractmethod
    def convert_memory(self, user_id: str) -> None:
        """Convert memory/custom instructions to SQL format."""

    @abstractmethod
    def get_required_files(self) -> List[str]:
        """Get list of required files for this provider."""

    @abstractmethod
    def get_optional_files(self) -> List[str]:
        """Get list of optional files for this provider."""

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return Config.SUPPORTED_PROVIDERS.get(self.name, {})


class ChatGPTProvider(MigrationProvider):
    """Migration provider for ChatGPT exports."""

    def __init__(self):
        """Initialize the ChatGPT provider."""
        super().__init__("chatgpt")

    def get_required_files(self) -> List[str]:
        """Get required files for ChatGPT migration."""
        return ["conversations.json"]

    def get_optional_files(self) -> List[str]:
        """Get optional files for ChatGPT migration."""
        return ["memory.txt"]

    def validate_data_files(self) -> bool:
        """Validate ChatGPT data files exist."""
        conversations_file = self.data_path / "conversations.json"
        memory_file = self.data_path / "memory.txt"

        if not conversations_file.exists() and not memory_file.exists():
            raise FileOperationError(
                f"No data files found in {self.data_path}. "
                "Please add conversations.json and/or memory.txt files"
            )

        if conversations_file.exists():
            print(f"Found conversations file: {conversations_file}")
        if memory_file.exists():
            print(f"Found memory file: {memory_file}")

        return True

    def convert_conversations(self, user_id: str) -> None:
        """Convert ChatGPT conversations to OpenWebUI format."""
        conversations_path = self.data_path / "conversations.json"

        if not conversations_path.exists():
            print("No conversations.json found. Skipping conversation conversion.")
            return

        print(f"Converting ChatGPT conversations for user: {user_id}")

        try:
            self.output_path.mkdir(parents=True, exist_ok=True)
            convert_file(str(conversations_path), user_id=user_id, outdir=str(self.output_path))
            print(f"Successfully converted conversations to {self.output_path}")
        except Exception as e:
            raise ProviderError(f"Failed to convert conversations: {e}") from e

    def convert_memory(self, user_id: str) -> None:
        """Convert ChatGPT memory to SQL format."""
        memory_path = self.data_path / "memory.txt"

        if not memory_path.exists():
            print("No memory.txt found. Skipping memory conversion.")
            return

        try:
            memories = parse_memory_file(str(memory_path))
            if memories:
                sql_content = create_memory_sql(memories, user_id=user_id, remove_existing=False)
                SQLFileManager.write_sql(sql_content, Path(Config.MEMORY_SQL_NAME))
                print(
                    f"Successfully converted {len(memories)} memory entries "
                    "(duplicates will be skipped)"
                )
            else:
                print("No memory entries found in the file")
        except Exception as e:
            raise ProviderError(f"Failed to convert memory: {e}") from e

    def generate_sql_from_json(self) -> None:
        """Generate SQL from converted JSON files."""
        if not self.output_path.exists():
            return

        cmd = [
            "python",
            "utils/create_sql.py",
            str(self.output_path),
            f"--tags={self.name}",
            f"--output={Config.CONVERSATIONS_SQL_NAME}",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ProviderError(f"Failed to create SQL: {result.stderr}")


class ProviderFactory:
    """Factory class for creating migration providers."""

    _providers = {"chatgpt": ChatGPTProvider}

    @classmethod
    def create(cls, provider_name: str) -> MigrationProvider:
        """Create a migration provider instance."""
        provider_class = cls._providers.get(provider_name)
        if not provider_class:
            raise UnsupportedProviderError(f"Unsupported provider: {provider_name}")
        return provider_class()

    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """Get list of supported provider names."""
        return list(cls._providers.keys())

    @classmethod
    def register_provider(cls, name: str, provider_class: type) -> None:
        """Register a new provider class."""
        if not issubclass(provider_class, MigrationProvider):
            raise TypeError("Provider class must inherit from MigrationProvider")
        cls._providers[name] = provider_class
