from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.api import api_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.api.v1.endpoints.health import router as health_router


configure_logging()
settings = get_settings()

app = FastAPI(title=f"{settings.app_name} API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:4176",
        "http://127.0.0.1:4176",
    ],
    allow_credentials=False,
    allow_headers=["*"],
    allow_methods=["*"],
)
app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")
