from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import pytest

from backend.app.schemas.nfse import NfseNormalizedDocument


FIXTURES_DIR = Path("backend/tests/fixtures/nfse")


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_nfse_contract_supports_abrasf() -> None:
    document = NfseNormalizedDocument(**_fixture("abrasf_service.json"))
    assert document.source_layout == "NFSE_ABRASF_204"


def test_nfse_contract_supports_national() -> None:
    document = NfseNormalizedDocument(**_fixture("national_service.json"))
    assert document.source_layout == "NFSE_NACIONAL_101"


def test_nfse_contract_requires_period() -> None:
    payload = _fixture("abrasf_service.json")
    payload["service_period"] = "2026/07"
    with pytest.raises(ValueError):
        NfseNormalizedDocument(**payload)


def test_nfse_contract_requires_decimal_value() -> None:
    document = NfseNormalizedDocument(**_fixture("abrasf_service.json"))
    assert document.service_amount == Decimal("1000.00")


def test_nfse_contract_normalizes_cnae() -> None:
    document = NfseNormalizedDocument(**_fixture("national_service.json"))
    assert document.cnae == "7311400"


def test_cancelled_nfse_does_not_count_as_revenue() -> None:
    document = NfseNormalizedDocument(**_fixture("cancelled_service.json"))
    assert document.can_count_as_revenue() is False


def test_cancelled_by_substitution_does_not_count_as_revenue() -> None:
    document = NfseNormalizedDocument(**_fixture("substituted_service.json"))
    assert document.can_count_as_revenue() is False


def test_active_nfse_can_count_as_revenue() -> None:
    document = NfseNormalizedDocument(**_fixture("abrasf_service.json"))
    assert document.can_count_as_revenue() is True


def test_unknown_status_does_not_count_automatically() -> None:
    document = NfseNormalizedDocument(**_fixture("substituted_service.json"))
    assert document.can_count_as_revenue() is False


def test_nfse_contract_excludes_personal_tomador_fields() -> None:
    payload = _fixture("abrasf_service.json")
    assert "email" not in json.dumps(payload)
