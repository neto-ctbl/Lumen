from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.services.integrations.econet.cache import (
    DEFAULT_ECONET_CACHE_TTL_DAYS,
    EconetCacheOperation,
    upsert_econet_cnae_cache,
)
from backend.app.services.integrations.econet.parser import (
    build_normalized_cnae_result,
    parse_cnae_detail,
    parse_empreendedor_individual,
    parse_lucro_presumido,
    parse_lucro_real_estimativa,
    parse_lucro_real_trimestral,
    parse_obligations_general,
    parse_obligations_simei,
    parse_obligations_simples,
    parse_simples_nacional,
)
from backend.tests.econet_test_utils import fixture_path, read_text


def _build_result():
    return build_normalized_cnae_result(
        detail=parse_cnae_detail(read_text(fixture_path("cnae_detail.html"))),
        presumed_profit=parse_lucro_presumido(read_text(fixture_path("tax_lucro_presumido.html"))),
        actual_profit_trimestral=parse_lucro_real_trimestral(read_text(fixture_path("tax_lucro_real_trimestral.html"))),
        actual_profit_estimativa=parse_lucro_real_estimativa(read_text(fixture_path("tax_lucro_real_estimativa.html"))),
        simples=parse_simples_nacional(read_text(fixture_path("tax_simples_nacional.html"))),
        mei=parse_empreendedor_individual(read_text(fixture_path("tax_empreendedor_individual.html"))),
        obligations_general=parse_obligations_general(read_text(fixture_path("obligations_pj_geral.html"))),
        obligations_simples=parse_obligations_simples(read_text(fixture_path("obligations_simples_prohibited.html"))),
        obligations_simei=parse_obligations_simei(read_text(fixture_path("obligations_simei_not_allowed.html"))),
    )


def test_cache_creates_new_cnae(db_session) -> None:
    result = _build_result()
    write = upsert_econet_cnae_cache(db_session, normalized_result=result)
    assert write.operation == EconetCacheOperation.CREATED
    assert db_session.scalar(select(EconetCnaeCache).where(EconetCnaeCache.cnae == result.cnae)) is not None


def test_cache_updates_when_hash_changes(db_session) -> None:
    result = _build_result()
    upsert_econet_cnae_cache(db_session, normalized_result=result)
    changed_payload = {
        **result.normalized_payload,
        "cnae": {
            **result.normalized_payload["cnae"],
            "description": "ATIVIDADE SINTETICA ALTERADA",
        },
    }
    changed = replace(
        result,
        description="ATIVIDADE SINTETICA ALTERADA",
        normalized_payload=changed_payload,
        content_hash="f" * 64,
    )
    write = upsert_econet_cnae_cache(db_session, normalized_result=changed)
    assert write.operation == EconetCacheOperation.UPDATED


def test_cache_unchanged_when_hash_matches(db_session) -> None:
    result = _build_result()
    upsert_econet_cnae_cache(db_session, normalized_result=result)
    write = upsert_econet_cnae_cache(db_session, normalized_result=result)
    assert write.operation == EconetCacheOperation.UNCHANGED


def test_cache_does_not_duplicate_cnae(db_session) -> None:
    result = _build_result()
    upsert_econet_cnae_cache(db_session, normalized_result=result)
    upsert_econet_cnae_cache(db_session, normalized_result=result)
    rows = db_session.scalars(select(EconetCnaeCache).where(EconetCnaeCache.cnae == result.cnae)).all()
    assert len(rows) == 1


def test_cache_sets_expiration(db_session) -> None:
    result = _build_result()
    retrieved_at = datetime(2026, 7, 21, tzinfo=timezone.utc)
    write = upsert_econet_cnae_cache(db_session, normalized_result=result, retrieved_at=retrieved_at)
    assert write.expires_at == retrieved_at + timedelta(days=DEFAULT_ECONET_CACHE_TTL_DAYS)


def test_cache_preserves_decimal_values(db_session) -> None:
    result = _build_result()
    upsert_econet_cnae_cache(db_session, normalized_result=result)
    row = db_session.scalar(select(EconetCnaeCache).where(EconetCnaeCache.cnae == result.cnae))
    assert row is not None
    assert row.presumed_profit_irpj_rate == Decimal("8")
    assert row.presumed_profit_csll_rate == Decimal("12")


def test_cache_persists_unmapped_obligations(db_session) -> None:
    result = _build_result()
    upsert_econet_cnae_cache(db_session, normalized_result=result)
    row = db_session.scalar(select(EconetCnaeCache).where(EconetCnaeCache.cnae == result.cnae))
    assert row is not None
    assert "DIRBI" in row.unmapped_obligations


def test_cache_dry_run_does_not_write(db_session) -> None:
    result = _build_result()
    write = upsert_econet_cnae_cache(db_session, normalized_result=result, dry_run=True)
    assert write.operation == EconetCacheOperation.WOULD_CREATE
    assert db_session.scalar(select(EconetCnaeCache).where(EconetCnaeCache.cnae == result.cnae)) is None
