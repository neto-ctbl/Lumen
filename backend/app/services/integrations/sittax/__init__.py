from backend.app.services.integrations.sittax.client import FixtureSittaxClient, SittaxClient
from backend.app.services.integrations.sittax.errors import (
    SittaxAuthenticationError,
    SittaxAuthorizationError,
    SittaxBusinessError,
    SittaxConfigurationError,
    SittaxContextMismatchError,
    SittaxError,
    SittaxRateLimitError,
    SittaxResponseError,
    SittaxSessionError,
    SittaxTransportError,
)
from backend.app.services.integrations.sittax.session import SittaxSession
from backend.app.services.integrations.sittax.sync import (
    SittaxCompanySyncResult,
    SittaxApuracaoSyncResult,
    build_fixture_sittax_client,
    sync_sittax_apuracoes,
    sync_sittax_companies,
)

__all__ = [
    "FixtureSittaxClient",
    "SittaxAuthenticationError",
    "SittaxAuthorizationError",
    "SittaxBusinessError",
    "SittaxClient",
    "SittaxConfigurationError",
    "SittaxContextMismatchError",
    "SittaxError",
    "SittaxRateLimitError",
    "SittaxResponseError",
    "SittaxSession",
    "SittaxSessionError",
    "SittaxTransportError",
    "SittaxApuracaoSyncResult",
    "SittaxCompanySyncResult",
    "build_fixture_sittax_client",
    "sync_sittax_apuracoes",
    "sync_sittax_companies",
]
