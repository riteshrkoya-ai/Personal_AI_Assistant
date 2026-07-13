from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import AsyncSessionLocal
from app.services.future_me_service import (
    cancel_future_me_goal,
    complete_future_me_task,
    create_future_me_goal,
    create_future_me_weekly_plan,
    list_user_future_me_goals,
    list_user_future_me_tasks,
)
from app.services.user_service import get_or_create_telegram_user

router = APIRouter(prefix="/future-me", tags=["future-me"])


class FutureMeGoalItem(BaseModel):
    id: int
    title: str
    description: str | None
    target_weeks: int
    target_date: date | None
    status: str
    source: str
    created_at: datetime


class FutureMeTaskItem(BaseModel):
    id: int
    goal_id: int
    day_number: int
    title: str
    description: str | None
    status: str
    due_date: date | None
    completed_at: datetime | None


class FutureMeGoalCreateRequest(BaseModel):
    telegram_chat_id: int
    title: str = Field(..., min_length=1)
    description: str | None = None
    target_weeks: int = 4
    source: str = "telegram"


class FutureMeGoalCreateResponse(BaseModel):
    user_id: int
    goal: FutureMeGoalItem


class FutureMeGoalListRequest(BaseModel):
    telegram_chat_id: int
    status: str | None = "active"
    limit: int = 20


class FutureMeGoalListResponse(BaseModel):
    user_id: int
    goals: list[FutureMeGoalItem]


class FutureMeGoalCancelRequest(BaseModel):
    telegram_chat_id: int
    goal_id: int


class FutureMeGoalCancelResponse(BaseModel):
    user_id: int
    goal_id: int
    cancelled: bool
    message: str


class FutureMeWeeklyPlanCreateRequest(BaseModel):
    telegram_chat_id: int
    goal_id: int
    days: int = 5


class FutureMeWeeklyPlanCreateResponse(BaseModel):
    user_id: int
    goal_id: int
    created: bool
    tasks: list[FutureMeTaskItem]
    message: str


class FutureMeTaskListRequest(BaseModel):
    telegram_chat_id: int
    goal_id: int | None = None
    status: str | None = None
    limit: int = 50


class FutureMeTaskListResponse(BaseModel):
    user_id: int
    tasks: list[FutureMeTaskItem]


class FutureMeTaskCompleteRequest(BaseModel):
    telegram_chat_id: int
    task_id: int


class FutureMeTaskCompleteResponse(BaseModel):
    user_id: int
    task_id: int
    completed: bool
    message: str


def to_future_me_goal_item(goal) -> FutureMeGoalItem:
    return FutureMeGoalItem(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        target_weeks=goal.target_weeks,
        target_date=goal.target_date,
        status=goal.status,
        source=goal.source,
        created_at=goal.created_at,
    )


def to_future_me_task_item(task) -> FutureMeTaskItem:
    return FutureMeTaskItem(
        id=task.id,
        goal_id=task.goal_id,
        day_number=task.day_number,
        title=task.title,
        description=task.description,
        status=task.status,
        due_date=task.due_date,
        completed_at=task.completed_at,
    )


@router.post("/goals", response_model=FutureMeGoalCreateResponse)
async def save_future_me_goal(
    request: FutureMeGoalCreateRequest,
) -> FutureMeGoalCreateResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        try:
            goal = await create_future_me_goal(
                session=session,
                user_id=user.id,
                title=request.title,
                description=request.description,
                target_weeks=request.target_weeks,
                source=request.source,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        await session.commit()

        return FutureMeGoalCreateResponse(
            user_id=user.id,
            goal=to_future_me_goal_item(goal),
        )


@router.post("/goals/list", response_model=FutureMeGoalListResponse)
async def list_future_me_goals(
    request: FutureMeGoalListRequest,
) -> FutureMeGoalListResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        goals = await list_user_future_me_goals(
            session=session,
            user_id=user.id,
            status=request.status,
            limit=request.limit,
        )

        return FutureMeGoalListResponse(
            user_id=user.id,
            goals=[to_future_me_goal_item(goal) for goal in goals],
        )


@router.post("/goals/cancel", response_model=FutureMeGoalCancelResponse)
async def cancel_goal(
    request: FutureMeGoalCancelRequest,
) -> FutureMeGoalCancelResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        cancelled = await cancel_future_me_goal(
            session=session,
            user_id=user.id,
            goal_id=request.goal_id,
        )

        await session.commit()

        if cancelled:
            return FutureMeGoalCancelResponse(
                user_id=user.id,
                goal_id=request.goal_id,
                cancelled=True,
                message="Future Me goal cancelled.",
            )

        return FutureMeGoalCancelResponse(
            user_id=user.id,
            goal_id=request.goal_id,
            cancelled=False,
            message="No active Future Me goal was found for this user.",
        )


@router.post("/weekly-plan", response_model=FutureMeWeeklyPlanCreateResponse)
async def create_weekly_plan(
    request: FutureMeWeeklyPlanCreateRequest,
) -> FutureMeWeeklyPlanCreateResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        tasks = await create_future_me_weekly_plan(
            session=session,
            user_id=user.id,
            goal_id=request.goal_id,
            days=request.days,
        )

        await session.commit()

        if tasks:
            return FutureMeWeeklyPlanCreateResponse(
                user_id=user.id,
                goal_id=request.goal_id,
                created=True,
                tasks=[to_future_me_task_item(task) for task in tasks],
                message="Future Me weekly plan is ready.",
            )

        return FutureMeWeeklyPlanCreateResponse(
            user_id=user.id,
            goal_id=request.goal_id,
            created=False,
            tasks=[],
            message="No active Future Me goal was found.",
        )


@router.post("/tasks/list", response_model=FutureMeTaskListResponse)
async def list_future_me_tasks(
    request: FutureMeTaskListRequest,
) -> FutureMeTaskListResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        tasks = await list_user_future_me_tasks(
            session=session,
            user_id=user.id,
            goal_id=request.goal_id,
            status=request.status,
            limit=request.limit,
        )

        return FutureMeTaskListResponse(
            user_id=user.id,
            tasks=[to_future_me_task_item(task) for task in tasks],
        )


@router.post("/tasks/complete", response_model=FutureMeTaskCompleteResponse)
async def complete_task(
    request: FutureMeTaskCompleteRequest,
) -> FutureMeTaskCompleteResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        completed = await complete_future_me_task(
            session=session,
            user_id=user.id,
            task_id=request.task_id,
        )

        await session.commit()

        if completed:
            return FutureMeTaskCompleteResponse(
                user_id=user.id,
                task_id=request.task_id,
                completed=True,
                message="Future Me task completed.",
            )

        return FutureMeTaskCompleteResponse(
            user_id=user.id,
            task_id=request.task_id,
            completed=False,
            message="No pending Future Me task was found for this user.",
        )