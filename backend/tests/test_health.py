from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_healthcheck_contract() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "lumen-api",
        "stage": "S1",
    }


def test_worker_healthcheck_contract() -> None:
    response = client.get("/api/v1/worker/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "lumen-worker",
        "mode": "stub",
        "stage": "S1",
    }
