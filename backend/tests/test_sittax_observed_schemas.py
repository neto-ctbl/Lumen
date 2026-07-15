from __future__ import annotations

from backend.tests.sittax_test_utils import (
    FIXTURES_DIR,
    SCHEMAS_DIR,
    iter_schema_paths,
    load_json,
    validate_instance,
)


FIXTURE_TO_SCHEMA = {
    "login_success.json": None,
    "companies_success.json": "sittax_company.schema.json",
    "apuracao_success.json": "sittax_apuracao.schema.json",
    "difal_with_guide.json": "sittax_difal.schema.json",
    "difal_without_guide.json": "sittax_difal.schema.json",
    "fiscal_documents_entry_page.json": "sittax_fiscal_document_page.schema.json",
    "fiscal_documents_exit_page.json": "sittax_fiscal_document_page.schema.json",
    "tasks_page.json": "sittax_task_page.schema.json",
    "company_panel_success.json": "sittax_company_panel.schema.json",
}


def test_all_sittax_schemas_are_valid_json_documents() -> None:
    schema_paths = iter_schema_paths()
    assert schema_paths, "Expected observed Sittax schemas to exist."
    for path in schema_paths:
        schema = load_json(path)
        assert isinstance(schema, dict), f"{path.name}: schema root must be an object"
        assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
        assert "Observed" in str(schema.get("title", "")), f"{path.name}: schema title should identify observed origin"


def test_sittax_fixtures_match_corresponding_schemas() -> None:
    for fixture_name, schema_name in FIXTURE_TO_SCHEMA.items():
        fixture = load_json(FIXTURES_DIR / fixture_name)
        if schema_name is None:
            assert isinstance(fixture, dict)
            assert "token" in fixture
            continue
        schema = load_json(SCHEMAS_DIR / schema_name)
        validate_instance(schema, fixture)


def test_expected_fixture_and_schema_inventory_exists() -> None:
    fixture_names = sorted(path.name for path in FIXTURES_DIR.glob("*.json"))
    schema_names = sorted(path.name for path in SCHEMAS_DIR.glob("sittax_*.schema.json"))
    assert fixture_names == sorted(FIXTURE_TO_SCHEMA)
    assert schema_names == [
        "sittax_apuracao.schema.json",
        "sittax_company.schema.json",
        "sittax_company_panel.schema.json",
        "sittax_difal.schema.json",
        "sittax_fiscal_document_page.schema.json",
        "sittax_task_page.schema.json",
    ]
