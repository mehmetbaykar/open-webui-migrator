"""Database operations module for OpenWebUI migrator."""

import sqlite3
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from utils.config import Config
from utils.exceptions import DatabaseError, UserNotFoundError, ValidationError


class DatabaseManager:
    """Manages database operations for the migrator."""

    def __init__(self, db_path: str = Config.LOCAL_DB_NAME):
        """Initialize the database manager."""
        self.db_path = db_path

    def create_backup(self) -> None:
        """Create a backup of the database."""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Database file not found: {self.db_path}")

        backup_path = Path(Config.LOCAL_DB_BACKUP_NAME)
        shutil.copy2(self.db_path, backup_path)

    def get_users(self) -> List[Tuple[str, str, str]]:
        """Get all users from the database.

        Returns:
            List of tuples containing (user_id, name, email)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, email FROM user ORDER BY created_at")
                return cursor.fetchall()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get users: {e}") from e

    def user_exists(self, user_id: str) -> bool:
        """Check if a user exists in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM user WHERE id = ?", (user_id,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to check user existence: {e}") from e

    def get_user_by_id(self, user_id: str) -> Optional[Tuple[str, str, str]]:
        """Get user details by ID.

        Returns:
            Tuple containing (user_id, name, email) or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email FROM user WHERE id = ?", (user_id,))
            return cursor.fetchone()

    def execute_sql_file(self, sql_file_path: str) -> None:
        """Execute SQL statements from a file."""
        if not Path(sql_file_path).exists():
            raise FileNotFoundError(f"SQL file not found: {sql_file_path}")

        with open(sql_file_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                self._execute_statements(conn, sql_content, sql_file_path)
            finally:
                conn.close()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to execute SQL file: {e}") from e

    def _execute_statements(
        self, conn: sqlite3.Connection, sql_content: str, sql_file_path: str
    ) -> None:
        """Execute SQL statements from content."""
        statements = sql_content.split(";\n")
        total_statements = len([s for s in statements if s.strip()])
        executed = 0

        for statement in statements:
            statement = statement.strip()
            if not statement:
                continue

            try:
                conn.execute(statement + ";")
                executed += 1
                if executed % 100 == 0:
                    print(f"Executed {executed}/{total_statements} statements...")
                    conn.commit()
            except sqlite3.Error as e:
                print(f"Error executing statement {executed + 1}: {e}")
                print(f"Statement preview: {statement[:100]}...")
                raise

        conn.commit()
        print(f"Successfully executed {executed} SQL statements from {sql_file_path}")

    def validate_database(self) -> bool:
        """Validate that the database has the expected schema."""
        required_tables = ["user", "chat", "tag", "memory"]

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}

                missing_tables = [
                    table for table in required_tables if table not in existing_tables
                ]

                if missing_tables:
                    raise ValidationError(f"Missing required tables: {', '.join(missing_tables)}")

                return True

        except sqlite3.Error as e:
            raise DatabaseError(f"Database validation failed: {e}") from e


class UserSelector:
    """Handles user selection logic."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize the user selector."""
        self.db_manager = db_manager

    def get_user_id(self) -> str:
        """Get user ID from environment or database with validation."""
        env_user_id = Config.get_env_user_id()

        if env_user_id:
            return self._validate_env_user(env_user_id)

        return self._select_user_from_database()

    def _validate_env_user(self, user_id: str) -> str:
        """Validate user ID from environment."""
        user = self.db_manager.get_user_by_id(user_id)

        if not user:
            raise UserNotFoundError(f"USER_ID '{user_id}' from environment not found in database")

        print(f"Using USER_ID from environment: {user_id}")
        print(f"Validated user: {user[1]} ({user[2]}) - ID: {user[0]}")
        return user_id

    def _select_user_from_database(self) -> str:
        """Select user from database interactively."""
        users = self.db_manager.get_users()

        if not users:
            raise UserNotFoundError(
                "No users found in database and no USER_ID provided in environment"
            )

        if len(users) == 1:
            user_id, name, email = users[0]
            print(f"Found single user: {name} ({email}) - ID: {user_id}")
            return user_id

        return self._prompt_user_selection(users)

    def _prompt_user_selection(self, users: List[Tuple[str, str, str]]) -> str:
        """Prompt user to select from multiple users."""
        print("\nMultiple users found:")
        for i, (uid, name, email) in enumerate(users, 1):
            print(f"{i}. {name} ({email}) - ID: {uid}")

        while True:
            try:
                choice = input(
                    "\nSelect user number for migration (or press Enter for first user): "
                ).strip()

                if not choice:
                    user_id = users[0][0]
                    print(f"Using first user: {users[0][1]} - ID: {user_id}")
                    return user_id

                choice_num = int(choice)
                if 1 <= choice_num <= len(users):
                    user_id = users[choice_num - 1][0]
                    print(f"Selected user: {users[choice_num - 1][1]} " f"- ID: {user_id}")
                    return user_id

                print(f"Invalid choice. Please enter a number " f"between 1 and {len(users)}")
            except ValueError:
                print("Invalid input. Please enter a number.")

    def validate_user_id(self, user_id: str) -> bool:
        """Validate if a user ID exists in the database."""
        return self.db_manager.user_exists(user_id)
