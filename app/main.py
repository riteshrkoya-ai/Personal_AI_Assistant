from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.database import create_database_tables
from app.api.memory import router as memory_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_database_tables()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI Personal Assistant MVP backend",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(memory_router)


@app.get("/")
async def root():
    return {
        "message": "AI Personal Assistant API is running",
        "docs": "/docs",
        "health": "/health",
    }