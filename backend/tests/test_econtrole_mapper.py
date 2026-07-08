from __future__ import annotations

import pytest

from backend.app.services.integrations.econtrole.mapper import EControleMappingError, map_econtrole_company_payload


def test_map_econtrole_company_payload_complete() -> None:
    payload = {
        "id": "123",
        "profile_id": "456",
        "cnpj": "19.163.109/0001-78",
        "razao_social": "AC SOARES LTDA",
        "nomeFantasia": "AC Soares",
        "apelido_pasta": "AC Soares",
        "situacao": "ATIVA",
        "inscricao_estadual": "ISENTO",
        "inscricao_municipal": "12345",
        "municipio": "Anapolis",
        "uf": "go",
        "cnaePrincipal": "8630-5/03",
        "cnaes_secundarios": ["8650-0/01"],
        "updated_at": "2026-07-07T10:00:00-03:00",
    }

    mapped = map_econtrole_company_payload(payload)

    assert mapped["econtrole_company_id"] == "123"
    assert mapped["econtrole_profile_id"] == "456"
    assert mapped["cnpj"] == "19163109000178"
    assert mapped["razao_social"] == "AC SOARES LTDA"
    assert mapped["nome_fantasia"] == "AC Soares"
    assert mapped["inscricao_estadual"] == "ISENTO"
    assert mapped["uf"] == "GO"
    assert mapped["updated_at_econtrole"].isoformat() == "2026-07-07T10:00:00-03:00"


def test_map_econtrole_company_payload_empty_ie_becomes_none() -> None:
    payload = {
        "cnpj": "19163109000178",
        "razao_social": "AC SOARES LTDA",
        "inscricaoEstadual": "   ",
    }

    mapped = map_econtrole_company_payload(payload)

    assert mapped["inscricao_estadual"] is None


@pytest.mark.parametrize(
    ("field", "payload"),
    [
        ("cnpj", {"razao_social": "AC SOARES LTDA"}),
        ("razao_social", {"cnpj": "19163109000178"}),
    ],
)
def test_map_econtrole_company_payload_missing_required_fields_raise(field: str, payload: dict[str, str]) -> None:
    with pytest.raises(EControleMappingError, match=field):
        map_econtrole_company_payload(payload)


def test_map_econtrole_company_payload_preserves_raw_payload() -> None:
    payload = {
        "cnpj": "19163109000178",
        "razaoSocial": "AC SOARES LTDA",
        "extra": {"source": "webhook"},
    }

    mapped = map_econtrole_company_payload(payload)

    assert mapped["raw_econtrole"] is payload
    assert mapped["raw_econtrole"]["extra"] == {"source": "webhook"}
