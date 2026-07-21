from __future__ import annotations

from backend.app.services.integrations.sittax.mapper import map_fiscal_document_item, map_fiscal_document_page


def test_map_fiscal_document_page_accepts_empty_list_as_success() -> None:
    page = map_fiscal_document_page(
        {"sucesso": True, "total": 20, "totalFiltrado": 0, "lista": []},
        direction="ENTRADA",
        page_number=0,
        page_size=15,
    )

    assert page.total == 20
    assert page.total_filtered == 0
    assert page.items == []


def test_map_fiscal_document_item_splits_cfops_string_and_hashes_missing_keys() -> None:
    item = map_fiscal_document_item(
        {
            "id": "",
            "chave_acesso": None,
            "numero": 123,
            "modelo": "55",
            "data_emissao": "2026-06-10T14:00:00Z",
            "data_competencia": "06/2026",
            "emitente_nome": "FORNECEDOR",
            "emitente_uf": "GO",
            "cfops": "5101,5102",
            "valor_total": 100.5,
            "status": 100,
            "importada": True,
        },
        direction="ENTRADA",
    )

    assert item.sittax_document_id is None
    assert item.source_document_key
    assert item.source_document_key != "123"
    assert item.cfops == ["5101", "5102"]
    assert item.status == "100"
    assert item.issuer_name == "FORNECEDOR"
    assert item.imported is True
