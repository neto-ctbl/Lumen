from fastapi import FastAPI

from backend.app.api.v1.api import api_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.api.v1.endpoints.health import router as health_router


configure_logging()
settings = get_settings()

app = FastAPI(title=f"{settings.app_name} API", version="0.2.0")
app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")
