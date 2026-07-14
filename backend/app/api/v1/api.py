from fastapi import APIRouter

from backend.app.api.v1.endpoints.auth import router as auth_router
from backend.app.api.v1.endpoints.integrations.acessorias import router as acessorias_integration_router
from backend.app.api.v1.endpoints.lumen import router as lumen_router
from backend.app.api.v1.endpoints.webhooks.econtrole import router as econtrole_webhook_router
from backend.app.api.v1.endpoints.worker import router as worker_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(acessorias_integration_router)
api_router.include_router(lumen_router)
api_router.include_router(econtrole_webhook_router)
api_router.include_router(worker_router, prefix="/worker", tags=["worker"])
