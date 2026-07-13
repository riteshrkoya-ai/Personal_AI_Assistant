from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import AsyncSessionLocal
from app.services.study_service import (
    cancel_study_plan,
    complete_study_task,
    create_study_plan,
    create_study_plan_reminders,
    list_user_study_plans,
    list_user_study_tasks,
)
from app.services.user_service import get_or_create_telegram_user

from app.core.config import get_settings

router = APIRouter(prefix="/study", tags=["study"])
settings = get_settings()

class StudyTaskItem(BaseModel):
    id: int
    study_plan_id: int
    day_number: int
    title: str
    description: str | None
    status: str
    completed_at: datetime | None


class StudyPlanItem(BaseModel):
    id: int
    topic: str
    goal: str | None
    status: str
    source: str
    created_at: datetime


class StudyPlanCreateRequest(BaseModel):
    telegram_chat_id: int
    topic: str = Field(..., min_length=1)
    goal: str | None = None
    days: int = 5
    source: str = "telegram"


class StudyPlanCreateResponse(BaseModel):
    user_id: int
    study_plan: StudyPlanItem
    tasks: list[StudyTaskItem]


class StudyPlanListRequest(BaseModel):
    telegram_chat_id: int
    status: str | None = "active"
    limit: int = 20


class StudyPlanListResponse(BaseModel):
    user_id: int
    study_plans: list[StudyPlanItem]


class StudyTaskListRequest(BaseModel):
    telegram_chat_id: int
    study_plan_id: int | None = None
    status: str | None = None
    limit: int = 50


class StudyTaskListResponse(BaseModel):
    user_id: int
    tasks: list[StudyTaskItem]


class StudyTaskCompleteRequest(BaseModel):
    telegram_chat_id: int
    task_id: int


class StudyTaskCompleteResponse(BaseModel):
    user_id: int
    task_id: int
    completed: bool
    message: str

class StudyPlanCancelRequest(BaseModel):
    telegram_chat_id: int
    study_plan_id: int


class StudyPlanCancelResponse(BaseModel):
    user_id: int
    study_plan_id: int
    cancelled: bool
    message: str

class StudyPlanRemindersCreateRequest(BaseModel):
    telegram_chat_id: int
    study_plan_id: int
    hour: int = 20
    minute: int = 0


class StudyPlanRemindersCreateResponse(BaseModel):
    user_id: int
    study_plan_id: int
    created: bool
    reminder_count: int
    message: str

def to_study_plan_item(study_plan) -> StudyPlanItem:
    return StudyPlanItem(
        id=study_plan.id,
        topic=study_plan.topic,
        goal=study_plan.goal,
        status=study_plan.status,
        source=study_plan.source,
        created_at=study_plan.created_at,
    )


def to_study_task_item(task) -> StudyTaskItem:
    return StudyTaskItem(
        id=task.id,
        study_plan_id=task.study_plan_id,
        day_number=task.day_number,
        title=task.title,
        description=task.description,
        status=task.status,
        completed_at=task.completed_at,
    )


@router.post("/plans", response_model=StudyPlanCreateResponse)
async def save_study_plan(
    request: StudyPlanCreateRequest,
) -> StudyPlanCreateResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        try:
            study_plan, tasks = await create_study_plan(
                session=session,
                user_id=user.id,
                topic=request.topic,
                goal=request.goal,
                days=request.days,
                source=request.source,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        await session.commit()

        return StudyPlanCreateResponse(
            user_id=user.id,
            study_plan=to_study_plan_item(study_plan),
            tasks=[to_study_task_item(task) for task in tasks],
        )


@router.post("/plans/list", response_model=StudyPlanListResponse)
async def list_study_plans(
    request: StudyPlanListRequest,
) -> StudyPlanListResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        study_plans = await list_user_study_plans(
            session=session,
            user_id=user.id,
            status=request.status,
            limit=request.limit,
        )

        return StudyPlanListResponse(
            user_id=user.id,
            study_plans=[to_study_plan_item(plan) for plan in study_plans],
        )


@router.post("/tasks/list", response_model=StudyTaskListResponse)
async def list_study_tasks(
    request: StudyTaskListRequest,
) -> StudyTaskListResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        tasks = await list_user_study_tasks(
            session=session,
            user_id=user.id,
            study_plan_id=request.study_plan_id,
            status=request.status,
            limit=request.limit,
        )

        return StudyTaskListResponse(
            user_id=user.id,
            tasks=[to_study_task_item(task) for task in tasks],
        )


@router.post("/tasks/complete", response_model=StudyTaskCompleteResponse)
async def complete_task(
    request: StudyTaskCompleteRequest,
) -> StudyTaskCompleteResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        completed = await complete_study_task(
            session=session,
            user_id=user.id,
            task_id=request.task_id,
        )

        await session.commit()

        if completed:
            return StudyTaskCompleteResponse(
                user_id=user.id,
                task_id=request.task_id,
                completed=True,
                message="Study task completed.",
            )

        return StudyTaskCompleteResponse(
            user_id=user.id,
            task_id=request.task_id,
            completed=False,
            message="No pending study task was found for this user.",
        )
    
@router.post("/plans/cancel", response_model=StudyPlanCancelResponse)
async def cancel_plan(
    request: StudyPlanCancelRequest,
) -> StudyPlanCancelResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        cancelled = await cancel_study_plan(
            session=session,
            user_id=user.id,
            study_plan_id=request.study_plan_id,
        )

        await session.commit()

        if cancelled:
            return StudyPlanCancelResponse(
                user_id=user.id,
                study_plan_id=request.study_plan_id,
                cancelled=True,
                message="Study plan cancelled.",
            )

        return StudyPlanCancelResponse(
            user_id=user.id,
            study_plan_id=request.study_plan_id,
            cancelled=False,
            message="No active study plan was found for this user.",
        )

@router.post("/plans/reminders", response_model=StudyPlanRemindersCreateResponse)
async def create_plan_reminders(
    request: StudyPlanRemindersCreateRequest,
) -> StudyPlanRemindersCreateResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        try:
            reminders = await create_study_plan_reminders(
                session=session,
                user_id=user.id,
                study_plan_id=request.study_plan_id,
                hour=request.hour,
                minute=request.minute,
                timezone_name=settings.timezone,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        await session.commit()

        if reminders:
            return StudyPlanRemindersCreateResponse(
                user_id=user.id,
                study_plan_id=request.study_plan_id,
                created=True,
                reminder_count=len(reminders),
                message="Study reminders created.",
            )

        return StudyPlanRemindersCreateResponse(
            user_id=user.id,
            study_plan_id=request.study_plan_id,
            created=False,
            reminder_count=0,
            message="No active study plan with pending tasks was found.",
        )