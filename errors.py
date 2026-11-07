"""Custom exceptions shared by every module."""


class ValidationError(ValueError):
    """Raised when user supplied data is invalid."""


class DatabaseError(Exception):
    """Raised when a database operation cannot be completed."""
