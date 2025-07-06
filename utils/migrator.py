"""Migration utilities for OpenWebUI migrator."""

import sys
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from utils.config import Config
from utils.database import DatabaseManager, UserSelector
from utils.docker_ops import DockerManager, DatabaseSync, ImageSync
from utils.providers import ProviderFactory
from utils.exceptions import (
    ProviderError,
    FileOperationError,
    ConversionError,
    DatabaseError,
    MigratorError,
)
from utils.chatgpt import get_ai_generated_images_to_copy

load_dotenv()


def get_user_id_from_database() -> str:
    """Get user ID from environment or database, with validation."""
    db_manager = DatabaseManager()
    user_selector = UserSelector(db_manager)
    return user_selector.get_user_id()


def stop_open_webui() -> None:
    """Stop the open-webui Docker container."""
    docker_manager = DockerManager()
    docker_manager.stop_container()


def copy_existing_database_from_docker() -> None:
    """Copy the existing database from the Docker container."""
    docker_manager = DockerManager()
    db_sync = DatabaseSync(docker_manager)
    db_sync.pull_database()


def create_backup_database_from_existing_database() -> None:
    """Create a backup of the existing database."""
    print("Creating backup of existing database...")
    db_manager = DatabaseManager()
    db_manager.create_backup()


def copy_ai_generated_images_to_docker(provider: str = "chatgpt") -> None:
    """Copy AI-generated images to the Docker volume's uploads directory."""
    output_path = Config.get_output_path(provider)

    if not output_path.exists():
        print(f"No output directory found for {provider}, skipping image copy.")
        return

    conversations = []
    for json_file in output_path.glob("*.json"):
        with open(json_file, "r", encoding="utf-8") as f:
            conversations.append(json.load(f))

    images_to_copy = get_ai_generated_images_to_copy(conversations)

    docker_manager = DockerManager()
    image_sync = ImageSync(docker_manager)
    image_sync.sync_images(images_to_copy)


def convert_conversation_to_sql(provider: str = "chatgpt", user_id: Optional[str] = None) -> str:
    """Convert conversation data to SQL format using provider-specific utilities."""
    print(f"Converting {provider} conversations to SQL...")

    migration_provider = ProviderFactory.create(provider)

    if not user_id:
        print("Getting user ID from database...")
        user_id = get_user_id_from_database()

    try:
        migration_provider.convert_conversations(user_id)
        migration_provider.generate_sql_from_json()
    except (ProviderError, FileOperationError, ConversionError) as e:
        print(f"Error converting conversations: {e}")
        sys.exit(1)

    return user_id


def convert_memory_to_sql(provider: str = "chatgpt", user_id: str = "user") -> None:
    """Convert memory data to SQL format using provider-specific utilities."""
    print(f"Converting {provider} memory to SQL...")

    migration_provider = ProviderFactory.create(provider)

    try:
        migration_provider.convert_memory(user_id)
    except (ProviderError, FileOperationError, ConversionError) as e:
        print(f"Error converting memory: {e}")
        sys.exit(1)


def run_migrations(provider: str = "chatgpt") -> None:
    """Run the SQL migrations on the database."""
    print("Running migrations...")

    db_manager = DatabaseManager()

    sql_files = [
        (Config.CONVERSATIONS_SQL_NAME, "conversations"),
        (Config.MEMORY_SQL_NAME, "memory"),
    ]

    for sql_file, migration_type in sql_files:
        if Path(sql_file).exists():
            print(f"Applying {migration_type} migration...")
            try:
                db_manager.execute_sql_file(sql_file)
            except (DatabaseError, FileNotFoundError, OSError) as e:
                print(f"Error applying {migration_type} migration: {e}")
                sys.exit(1)
        else:
            print(f"No {sql_file} found, skipping {migration_type} migration.")

    docker_manager = DockerManager()
    db_sync = DatabaseSync(docker_manager)
    db_sync.push_database()

    copy_ai_generated_images_to_docker(provider)


def clear_artifacts() -> None:
    """Clean up generated files."""
    print("Cleaning up artifacts...")

    for artifact in Config.get_artifacts_to_clean():
        artifact_path = Path(artifact)
        if artifact_path.exists():
            if artifact_path.is_dir():
                shutil.rmtree(artifact_path)
            else:
                artifact_path.unlink()


def start_open_webui() -> None:
    """Start the open-webui Docker container."""
    docker_manager = DockerManager()
    docker_manager.start_container()


def migrate_provider(provider: str = "chatgpt") -> None:
    """Migrate data for a specific provider."""
    print(f"\n{'='*60}")
    print(f"Starting migration for {provider}...")
    print(f"{'='*60}\n")

    provider_path = Config.get_provider_path(provider)
    if not provider_path.exists():
        print(
            f"Error: {provider_path} directory not found. Please create it and add your data files."
        )
        sys.exit(1)

    migration_provider = ProviderFactory.create(provider)

    try:
        migration_provider.validate_data_files()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        stop_open_webui()
        copy_existing_database_from_docker()
        create_backup_database_from_existing_database()

        user_id = convert_conversation_to_sql(provider)
        convert_memory_to_sql(provider, user_id=user_id)

        run_migrations(provider)
        start_open_webui()

        print(f"\n{'='*60}")
        print("MIGRATION SUMMARY")
        print(f"{'='*60}")

        clear_artifacts()

        print(f"\n✅ Migration completed successfully for {provider}!")
        print(f"{'='*60}\n")
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(1)
    except MigratorError as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
    except (OSError, IOError) as e:
        print(f"File system error during migration: {e}")
        sys.exit(2)
    except ValueError as e:
        print(f"Invalid value during migration: {e}")
        sys.exit(2)


def migrate_all() -> None:
    """Migrate all supported providers."""
    print("Starting migration for all supported providers...")

    supported_providers = ProviderFactory.get_supported_providers()
    migrated_any = False

    for provider_name in supported_providers:
        provider_path = Config.get_provider_path(provider_name)

        if not provider_path.exists():
            print(f"No {provider_name} data folder found, skipping...")
            continue

        try:
            migration_provider = ProviderFactory.create(provider_name)
            migration_provider.validate_data_files()

            print(f"Found {provider_name} data, migrating...")
            migrate_provider(provider_name)
            migrated_any = True

        except FileNotFoundError:
            print(f"Found {provider_name} folder but no valid data files, skipping...")
        except (ProviderError, FileOperationError) as e:
            print(f"Error checking {provider_name}: {e}")

    if not migrated_any:
        print("No data found for any supported providers.")
        print("Please add your exported data to the appropriate folders under data/")
        print("Supported providers: " + ", ".join(supported_providers))


def list_supported_providers() -> Dict[str, Dict[str, Any]]:
    """List all supported providers and their requirements."""
    print("Supported providers:")

    for provider_name, provider_info in Config.SUPPORTED_PROVIDERS.items():
        print(f"\n{provider_info['name']}:")
        print(f"  Folder: {Config.get_provider_path(provider_name)}")

        files = provider_info["required_files"] + provider_info.get("optional_files", [])
        print(f"  Files: {', '.join(files)}")
        print(f"  Info: {provider_info['description']}")

    return Config.SUPPORTED_PROVIDERS
