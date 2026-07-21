from __future__ import annotations

from backend.app.services.integrations.sittax.mapper import map_task_item, map_task_page


def test_map_task_page_accepts_empty_list_as_success() -> None:
    page = map_task_page(
        {"sucesso": True, "total": 25, "totalFiltrado": 0, "lista": []},
        page_number=0,
        page_size=25,
    )

    assert page.total == 25
    assert page.total_filtered == 0
    assert page.items == []


def test_map_task_item_normalizes_numeric_fields_and_period() -> None:
    item = map_task_item(
        {
            "id": 10,
            "guid": "guid-1",
            "titulo": "Transmitir DAS",
            "descricaoString": "Descricao observada",
            "nomeEmpresa": "Empresa Exemplo",
            "periodo": "06/2026",
            "status": 2,
            "usuarioId": 9,
            "usuarioNome": "Usuario",
            "dataCriacao": "2026-07-01T08:10:00Z",
            "dataFimProcessamento": "2026-07-01T08:11:30Z",
            "possuiArquivo": True,
            "extensaoArquivo": 4,
            "nomeArquivo": "comprovante.pdf",
            "tempoProcessamento": "90.123456",
        }
    )

    assert item.source_task_key == "10"
    assert item.period_reference == "2026-06"
    assert item.status == "2"
    assert item.status_code == 2
    assert item.source_user_id == "9"
    assert item.task_type == "Transmitir DAS"
    assert item.file_name == "comprovante.pdf"
    assert item.file_extension == ".pdf"
    assert item.file_extension_code == 4
    assert str(item.processing_time_seconds) == "90.12"


def test_map_task_item_accepts_textual_status_and_extension_fixture_shapes() -> None:
    item = map_task_item(
        {
            "id": "task-1",
            "titulo": "Transmitir DAS sintetico",
            "nomeEmpresa": "EMPRESA EXEMPLO A",
            "periodo": "06/2026",
            "status": "CONCLUIDA",
            "extensaoArquivo": ".pdf",
            "nomeArquivo": "comprovante_sintetico.pdf",
        }
    )

    assert item.status == "CONCLUIDA"
    assert item.status_code is None
    assert item.file_extension == ".pdf"
    assert item.file_extension_code is None
