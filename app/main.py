from fastapi import FastAPI

app = FastAPI(
    title="AI Personal Assistant API",
    version="0.1.0",
    description="MVP backend for a multi-user Telegram-based AI personal assistant.",
)


@app.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "AI Personal Assistant API",
        "version": "0.1.0",
    }


@app.get("/")
async def root() -> dict:
    return {
        "message": "AI Personal Assistant API is running.",
        "docs": "/docs",
        "health": "/health",
    }