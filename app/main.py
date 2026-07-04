from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.chat import router as chat_router

app = FastAPI(
    title="AI Personal Assistant API",
    version="0.1.0",
    description="MVP backend for a multi-user Telegram-based AI personal assistant.",
)

app.include_router(health_router)
app.include_router(chat_router)


@app.get("/")
async def root() -> dict:
    return {
        "message": "AI Personal Assistant API is running.",
        "docs": "/docs",
        "health": "/health",
    }