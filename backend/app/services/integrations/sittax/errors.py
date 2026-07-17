from __future__ import annotations


class SittaxError(RuntimeError):
    pass


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
