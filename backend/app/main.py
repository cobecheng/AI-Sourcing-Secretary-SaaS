from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import health, mock


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Chat-first AI sourcing secretary backend foundation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(mock.router)

