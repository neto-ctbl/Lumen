from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
def worker_health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "lumen-worker",
        "mode": "stub",
        "stage": "S1",
    }
