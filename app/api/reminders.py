from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import AsyncSessionLocal
from app.services.reminder_service import (
    cancel_user_reminder,
    create_reminder,
    list_user_reminders,
)
from app.services.user_service import get_or_create_telegram_user

router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderCreateRequest(BaseModel):
    telegram_chat_id: int
    message: str = Field(..., min_length=1)
    scheduled_time: datetime
    source: str = "telegram"


class ReminderItem(BaseModel):
    id: int
    message: str
    scheduled_time: datetime
    status: str
    source: str


class ReminderCreateResponse(BaseModel):
    reminder_id: int
    user_id: int
    message: str
    scheduled_time: datetime
    status: str


class ReminderListRequest(BaseModel):
    telegram_chat_id: int
    status: str = "pending"
    limit: int = 20


class ReminderListResponse(BaseModel):
    user_id: int
    reminders: list[ReminderItem]


class ReminderCancelRequest(BaseModel):
    telegram_chat_id: int
    reminder_id: int


class ReminderCancelResponse(BaseModel):
    user_id: int
    reminder_id: int
    cancelled: bool
    message: str


@router.post("", response_model=ReminderCreateResponse)
async def save_reminder(request: ReminderCreateRequest) -> ReminderCreateResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        try:
            reminder = await create_reminder(
                session=session,
                user_id=user.id,
                message=request.message,
                scheduled_time=request.scheduled_time,
                source=request.source,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        await session.commit()

        return ReminderCreateResponse(
            reminder_id=reminder.id,
            user_id=user.id,
            message=reminder.message,
            scheduled_time=reminder.scheduled_time,
            status=reminder.status,
        )


@router.post("/list", response_model=ReminderListResponse)
async def list_reminders(request: ReminderListRequest) -> ReminderListResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        reminders = await list_user_reminders(
            session=session,
            user_id=user.id,
            status=request.status,
            limit=request.limit,
        )

        return ReminderListResponse(
            user_id=user.id,
            reminders=[
                ReminderItem(
                    id=reminder.id,
                    message=reminder.message,
                    scheduled_time=reminder.scheduled_time,
                    status=reminder.status,
                    source=reminder.source,
                )
                for reminder in reminders
            ],
        )


@router.post("/cancel", response_model=ReminderCancelResponse)
async def cancel_reminder(request: ReminderCancelRequest) -> ReminderCancelResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        cancelled = await cancel_user_reminder(
            session=session,
            user_id=user.id,
            reminder_id=request.reminder_id,
        )

        await session.commit()

        if not cancelled:
            return ReminderCancelResponse(
                user_id=user.id,
                reminder_id=request.reminder_id,
                cancelled=False,
                message="No pending reminder was found for this user.",
            )

        return ReminderCancelResponse(
            user_id=user.id,
            reminder_id=request.reminder_id,
            cancelled=True,
            message="Reminder cancelled successfully.",
        )