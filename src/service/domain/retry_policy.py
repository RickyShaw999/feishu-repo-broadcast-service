from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    initial_delay_seconds: int = 30
    max_delay_seconds: int = 600
    factor: int = 2

    def delay_for_attempt(self, attempts: int) -> int:
        exponent = max(attempts - 1, 0)
        return min(self.initial_delay_seconds * (self.factor**exponent), self.max_delay_seconds)

    def exhausted(self, attempts: int) -> bool:
        return attempts >= self.max_attempts

