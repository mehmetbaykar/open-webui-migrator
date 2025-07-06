"""Custom exceptions for OpenWebUI migrator."""


class MigratorError(Exception):
    """Base exception for migrator errors."""


class DatabaseError(MigratorError):
    """Database-related errors."""


class DockerError(MigratorError):
    """Docker-related errors."""


class ProviderError(MigratorError):
    """Provider-related errors."""


class FileOperationError(MigratorError):
    """File operation errors."""


class ValidationError(MigratorError):
    """Validation errors."""


class UserNotFoundError(DatabaseError):
    """User not found in database."""


class ContainerNotFoundError(DockerError):
    """Docker container not found."""


class ContainerNotRunningError(DockerError):
    """Docker container not running."""


class UnsupportedProviderError(ProviderError):
    """Unsupported provider specified."""


class MigrationError(MigratorError):
    """General migration error."""


class UserSelectionError(MigratorError):
    """Raised when user selection fails."""


class ConfigurationError(MigratorError):
    """Raised when configuration is invalid."""


class ConversionError(MigratorError):
    """Raised when data conversion fails."""
