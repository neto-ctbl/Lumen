from fastapi import APIRouter

from backend.app.api.v1.endpoints.worker import router as worker_router


api_router = APIRouter()
api_router.include_router(worker_router, prefix="/worker", tags=["worker"])
