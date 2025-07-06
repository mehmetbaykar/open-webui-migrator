"""File operations module for OpenWebUI migrator."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


class FileManager:
    """Manages file operations with proper error handling."""

    @staticmethod
    def load_json(file_path: Path) -> Dict[str, Any]:
        """Load JSON file with error handling.

        Args:
            file_path: Path to the JSON file

        Returns:
            Parsed JSON content

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        if not file_path.exists():
            raise FileNotFoundError(f"JSON file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in {file_path}: {e.msg}", e.doc, e.pos)

    @staticmethod
    def save_json(data: Dict[str, Any], file_path: Path) -> None:
        """Save data to JSON file with error handling.

        Args:
            data: Data to save
            file_path: Path to save the file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def read_text(file_path: Path) -> str:
        """Read text file with error handling.

        Args:
            file_path: Path to the text file

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Text file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def write_text(content: str, file_path: Path) -> None:
        """Write text to file with error handling.

        Args:
            content: Text content to write
            file_path: Path to save the file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def copy_file(source: Path, destination: Path) -> None:
        """Copy file with error handling.

        Args:
            source: Source file path
            destination: Destination file path

        Raises:
            FileNotFoundError: If source file doesn't exist
        """
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    @staticmethod
    def remove_path(path: Path) -> None:
        """Remove file or directory safely.

        Args:
            path: Path to remove
        """
        if not path.exists():
            return

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    @staticmethod
    def list_files(directory: Path, pattern: str = "*") -> List[Path]:
        """List files in directory matching pattern.

        Args:
            directory: Directory to search
            pattern: Glob pattern to match

        Returns:
            List of matching file paths
        """
        if not directory.exists():
            return []

        return list(directory.glob(pattern))


class SQLFileManager:
    """Manages SQL file operations."""

    @staticmethod
    def read_sql(file_path: Path) -> str:
        """Read SQL file content.

        Args:
            file_path: Path to SQL file

        Returns:
            SQL content

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"SQL file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def write_sql(content: str, file_path: Path) -> None:
        """Write SQL content to file.

        Args:
            content: SQL content
            file_path: Path to save SQL file
        """
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
