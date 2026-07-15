from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import threading

import httpx
import pytest

from backend.app.services.integrations.sittax.errors import SittaxSessionError
from backend.app.services.integrations.sittax.session import SittaxSession


def build_session() -> SittaxSession:
    return SittaxSession(
        auth_base_url="https://autenticacao.sittax.com.br",
        api_base_url="https://api.sittax.com.br",
        apuracao_base_url="https://apuracao.sittax.com.br",
        timeout_seconds=20,
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))),
    )


def test_session_uses_single_http_client_and_closes_it() -> None:
    session = build_session()

    assert session.http_client is session.http_client
    session.close()

    assert session.is_closed is True


def test_session_repr_does_not_expose_token_or_password() -> None:
    session = build_session()
    with session.exclusive():
        session.mark_authenticated(
            token="secret-token",
            office_id="esc-1",
            office_name="Escritorio Exemplo",
            user_id="usr-1",
            user_role="ADMIN",
        )

    text = repr(session)

    assert "secret-token" not in text
    assert "password" not in text.lower()


def test_session_context_fields_start_null_and_are_not_changed_by_listing() -> None:
    session = build_session()

    assert session.active_company_cnpj is None
    assert session.active_period is None


def test_session_requires_exclusive_usage() -> None:
    session = build_session()

    with pytest.raises(SittaxSessionError, match="session.exclusive"):
        session.mark_authenticated(
            token="secret-token",
            office_id="esc-1",
            office_name="Escritorio Exemplo",
            user_id="usr-1",
            user_role="ADMIN",
        )


def test_session_lock_blocks_parallel_use_and_releases_after_exception() -> None:
    session = build_session()
    entered_first = threading.Event()
    release_first = threading.Event()
    entered_second = threading.Event()

    def first_worker() -> None:
        with session.exclusive():
            entered_first.set()
            release_first.wait(timeout=1)

    def second_worker() -> None:
        entered_first.wait(timeout=1)
        with session.exclusive():
            entered_second.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future: Future[None] = executor.submit(first_worker)
        second_future: Future[None] = executor.submit(second_worker)
        assert entered_first.wait(timeout=1) is True
        assert entered_second.wait(timeout=0.05) is False
        release_first.set()
        second_future.result(timeout=1)
        first_future.result(timeout=1)

    with pytest.raises(RuntimeError):
        with session.exclusive():
            raise RuntimeError("boom")

    with session.exclusive():
        session.mark_authenticated(
            token="second-token",
            office_id="esc-2",
            office_name="Escritorio Exemplo",
            user_id="usr-2",
            user_role="ADMIN",
        )


def test_closed_session_rejects_further_use() -> None:
    session = build_session()
    session.close()

    with pytest.raises(SittaxSessionError, match="closed"):
        with session.exclusive():
            pass
