"""Domain errors raised by the service layer.

Messages are user-facing Korean; FastAPI and MCP map them to their own transports.
"""

from __future__ import annotations


class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    code = "not_found"


class ConflictError(DomainError):
    code = "conflict"


class ValidationError(DomainError):
    code = "validation_error"


class InvalidTransitionError(ValidationError):
    code = "invalid_transition"
