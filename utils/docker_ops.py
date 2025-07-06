"""Docker operations module for OpenWebUI migrator."""

import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any
from utils.config import Config
from utils.exceptions import DockerError


class DockerManager:
    """Manages Docker container operations."""

    def __init__(self, container_name: str = Config.CONTAINER_NAME):
        """Initialize the Docker manager."""
        self.container_name = container_name

    def stop_container(self) -> None:
        """Stop the Docker container."""
        print(f"Stopping {self.container_name} container...")
        result = subprocess.run(
            ["docker", "stop", self.container_name], capture_output=True, text=True, check=False
        )
        if result.returncode != 0 and "No such container" not in result.stderr:
            raise DockerError(f"Failed to stop container: {result.stderr}")

    def start_container(self) -> None:
        """Start the Docker container."""
        print(f"Starting {self.container_name} container...")
        result = subprocess.run(
            ["docker", "start", self.container_name], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise DockerError(f"Failed to start container: {result.stderr}")

    def copy_from_container(self, container_path: str, local_path: str) -> None:
        """Copy a file from the Docker container to local filesystem."""
        print(f"Copying {container_path} from container to {local_path}...")
        result = subprocess.run(
            ["docker", "cp", f"{self.container_name}:{container_path}", local_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise DockerError(f"Failed to copy from container: {result.stderr}")

    def copy_to_container(self, local_path: str, container_path: str) -> None:
        """Copy a file from local filesystem to the Docker container."""
        result = subprocess.run(
            ["docker", "cp", local_path, f"{self.container_name}:{container_path}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise DockerError(f"Failed to copy to container: {result.stderr}")

    def exec_command(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute a command in the Docker container."""
        full_command = ["docker", "exec", self.container_name] + command
        result = subprocess.run(full_command, capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            raise DockerError(f"Command failed in container: {result.stderr}")
        return result

    def create_directory(self, container_path: str) -> None:
        """Create a directory in the Docker container."""
        try:
            self.exec_command(["mkdir", "-p", container_path])
        except DockerError:
            pass

    def container_exists(self) -> bool:
        """Check if the container exists."""
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return self.container_name in result.stdout.splitlines()

    def is_container_running(self) -> bool:
        """Check if the container is running."""
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, check=False
        )
        return self.container_name in result.stdout.splitlines()


class DatabaseSync:
    """Handles database synchronization with Docker container."""

    def __init__(self, docker_manager: DockerManager):
        """Initialize the database sync."""
        self.docker = docker_manager

    def pull_database(self) -> None:
        """Pull database from Docker container to local filesystem."""
        print("Copying database from Docker container...")
        self.docker.copy_from_container(Config.CONTAINER_DB_PATH, Config.LOCAL_DB_NAME)

    def push_database(self) -> None:
        """Push database from local filesystem to Docker container."""
        print("Copying updated database back to Docker container...")
        self.docker.copy_to_container(Config.LOCAL_DB_NAME, Config.CONTAINER_DB_PATH)


class ImageSync:
    """Handles image synchronization with Docker container."""

    def __init__(self, docker_manager: DockerManager):
        """Initialize the image sync."""
        self.docker = docker_manager

    def sync_images(self, images_to_copy: List[Tuple[str, str]]) -> Tuple[int, int]:
        """Sync AI-generated images to Docker container.

        Args:
            images_to_copy: List of tuples (source_path, destination_name)

        Returns:
            Tuple of (successful_copies, failed_copies)
        """
        if not images_to_copy:
            print("No AI-generated images to copy.")
            return 0, 0

        print(f"Found {len(images_to_copy)} AI-generated images to copy.")

        self.docker.create_directory(Config.CONTAINER_UPLOADS_PATH)

        successful = 0
        failed = 0

        for source_path, dest_name in images_to_copy:
            if not Path(source_path).exists():
                print(f"Source file not found: {source_path}")
                failed += 1
                continue

            try:
                dest_path = f"{Config.CONTAINER_UPLOADS_PATH}/{dest_name}"
                self.docker.copy_to_container(source_path, dest_path)
                successful += 1
            except DockerError as e:
                print(f"Failed to copy {source_path}: {e}")
                failed += 1

        print(f"Successfully copied {successful} AI-generated images.")
        if failed > 0:
            print(f"Failed to copy {failed} images.")

        return successful, failed

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status information."""
        return {
            "container_name": self.docker.container_name,
            "uploads_path": Config.CONTAINER_UPLOADS_PATH,
        }
