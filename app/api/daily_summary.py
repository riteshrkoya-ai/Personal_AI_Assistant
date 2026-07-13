from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.daily_summary_service import build_daily_summary
from app.services.user_service import get_or_create_telegram_user

router = APIRouter(prefix="/daily-summary", tags=["daily-summary"])

settings = get_settings()


class DailySummaryRequest(BaseModel):
    telegram_chat_id: int


class DailySummaryResponse(BaseModel):
    user_id: int
    summary_text: str
    counts: dict


@router.post("", response_model=DailySummaryResponse)
async def get_daily_summary(
    request: DailySummaryRequest,
) -> DailySummaryResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        summary = await build_daily_summary(
            session=session,
            user_id=user.id,
            timezone_name=settings.timezone,
        )

        return DailySummaryResponse(
            user_id=user.id,
            summary_text=summary["summary_text"],
            counts=summary["counts"],
        )