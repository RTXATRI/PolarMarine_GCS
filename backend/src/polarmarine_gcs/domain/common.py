from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class DomainError(Exception):
    code = "DOMAIN_ERROR"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    code = "NOT_FOUND"


class ConflictError(DomainError):
    code = "CONFLICT"


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"


class UnavailableError(DomainError):
    code = "UNAVAILABLE"


class StableCode(StrEnum):
    """Base for stable protocol enums represented by English strings."""
