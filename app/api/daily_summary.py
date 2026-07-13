from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.daily_summary_service import (
    build_daily_summary,
    disable_daily_summary_setting,
    list_due_daily_summary_settings,
    mark_daily_summary_sent,
    update_daily_summary_setting,
)
from app.services.user_service import get_or_create_telegram_user

router = APIRouter(prefix="/daily-summary", tags=["daily-summary"])

settings = get_settings()


class DailySummaryRequest(BaseModel):
    telegram_chat_id: int


class DailySummaryResponse(BaseModel):
    user_id: int
    summary_text: str
    counts: dict

class DailySummarySettingUpdateRequest(BaseModel):
    telegram_chat_id: int
    hour: int = 20
    minute: int = 0


class DailySummarySettingResponse(BaseModel):
    user_id: int
    enabled: bool
    hour: int
    minute: int
    timezone: str
    message: str


class DailySummaryDisableRequest(BaseModel):
    telegram_chat_id: int


class DueDailySummaryItem(BaseModel):
    setting_id: int
    telegram_chat_id: int
    summary_text: str


class DueDailySummaryListRequest(BaseModel):
    limit: int = 50


class DueDailySummaryListResponse(BaseModel):
    due_summaries: list[DueDailySummaryItem]


class DailySummaryMarkSentRequest(BaseModel):
    setting_id: int


class DailySummaryMarkSentResponse(BaseModel):
    marked: bool


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
    
@router.post("/settings", response_model=DailySummarySettingResponse)
async def update_summary_settings(
    request: DailySummarySettingUpdateRequest,
) -> DailySummarySettingResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        setting = await update_daily_summary_setting(
            session=session,
            user_id=user.id,
            hour=request.hour,
            minute=request.minute,
            timezone_name=settings.timezone,
        )

        await session.commit()

        return DailySummarySettingResponse(
            user_id=user.id,
            enabled=setting.is_enabled,
            hour=setting.hour,
            minute=setting.minute,
            timezone=setting.timezone,
            message="Daily summary schedule updated.",
        )


@router.post("/settings/disable", response_model=DailySummarySettingResponse)
async def disable_summary_settings(
    request: DailySummaryDisableRequest,
) -> DailySummarySettingResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        setting = await disable_daily_summary_setting(
            session=session,
            user_id=user.id,
            timezone_name=settings.timezone,
        )

        await session.commit()

        return DailySummarySettingResponse(
            user_id=user.id,
            enabled=setting.is_enabled,
            hour=setting.hour,
            minute=setting.minute,
            timezone=setting.timezone,
            message="Daily summary disabled.",
        )


@router.post("/due", response_model=DueDailySummaryListResponse)
async def list_due_summaries(
    request: DueDailySummaryListRequest,
) -> DueDailySummaryListResponse:
    async with AsyncSessionLocal() as session:
        due_settings = await list_due_daily_summary_settings(
            session=session,
            now_utc=datetime.now(timezone.utc),
            limit=request.limit,
        )

        due_items: list[DueDailySummaryItem] = []

        for setting, telegram_chat_id in due_settings:
            summary = await build_daily_summary(
                session=session,
                user_id=setting.user_id,
                timezone_name=setting.timezone,
            )

            due_items.append(
                DueDailySummaryItem(
                    setting_id=setting.id,
                    telegram_chat_id=telegram_chat_id,
                    summary_text=summary["summary_text"],
                )
            )

        return DueDailySummaryListResponse(due_summaries=due_items)


@router.post("/mark-sent", response_model=DailySummaryMarkSentResponse)
async def mark_summary_sent(
    request: DailySummaryMarkSentRequest,
) -> DailySummaryMarkSentResponse:
    timezone_obj = ZoneInfo(settings.timezone)
    today = datetime.now(timezone_obj).date()

    async with AsyncSessionLocal() as session:
        marked = await mark_daily_summary_sent(
            session=session,
            setting_id=request.setting_id,
            sent_date=today,
        )

        await session.commit()

        return DailySummaryMarkSentResponse(marked=marked)