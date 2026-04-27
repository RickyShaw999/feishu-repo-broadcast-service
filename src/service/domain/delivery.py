from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryResult:
    success: bool
    retryable: bool
    terminal: bool
    status_code: int | None = None
    response_body: str | None = None
    error: str | None = None

    @classmethod
    def delivered(cls, *, status_code: int | None = None, response_body: str | None = None) -> "DeliveryResult":
        return cls(success=True, retryable=False, terminal=True, status_code=status_code, response_body=response_body)

    @classmethod
    def retry(cls, *, status_code: int | None = None, response_body: str | None = None, error: str | None = None) -> "DeliveryResult":
        return cls(success=False, retryable=True, terminal=False, status_code=status_code, response_body=response_body, error=error)

    @classmethod
    def fail(cls, *, status_code: int | None = None, response_body: str | None = None, error: str | None = None) -> "DeliveryResult":
        return cls(success=False, retryable=False, terminal=True, status_code=status_code, response_body=response_body, error=error)

