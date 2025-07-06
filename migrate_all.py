"""Main migration script for OpenWebUI migrator."""

import sys
from typing import NoReturn
from utils.migrator import migrate_all
from utils.exceptions import MigratorError, DatabaseError, DockerError


def main() -> NoReturn:
    """Run the migration process."""
    try:
        migrate_all()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(1)
    except (MigratorError, DatabaseError, DockerError) as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
    except (OSError, IOError) as e:
        print(f"File system error: {e}")
        sys.exit(2)
    except ValueError as e:
        print(f"Invalid value: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
