from __future__ import annotations

from typing import Any


class SittaxError(RuntimeError):
    def __init__(self, message: str, *, diagnostic: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


class SittaxConfigurationError(SittaxError, ValueError):
    pass


class SittaxAuthenticationError(SittaxError):
    pass


class SittaxAuthorizationError(SittaxError):
    pass


class SittaxRateLimitError(SittaxError):
    pass


class SittaxResponseError(SittaxError):
    pass


class SittaxTransportError(SittaxError):
    pass


class SittaxBusinessError(SittaxError):
    pass


class SittaxContextMismatchError(SittaxError):
    pass


class SittaxSessionError(SittaxError):
    pass


class SittaxPaginationError(SittaxError):
    pass
