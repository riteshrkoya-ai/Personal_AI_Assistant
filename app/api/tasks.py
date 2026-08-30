from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import AsyncSessionLocal
from app.services.task_service import (
    complete_user_task,
    create_task,
    delete_user_task,
    list_user_tasks,
)
from app.services.user_service import get_or_create_telegram_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    telegram_chat_id: int
    title: str = Field(..., min_length=1)
    due_date: datetime | None = None
    source: str = "telegram"


class TaskItem(BaseModel):
    id: int
    title: str
    due_date: datetime | None
    status: str
    source: str


class TaskCreateResponse(BaseModel):
    task_id: int
    user_id: int
    title: str
    due_date: datetime | None
    status: str


class TaskListRequest(BaseModel):
    telegram_chat_id: int
    status: str = "pending"
    limit: int = 20


class TaskListResponse(BaseModel):
    user_id: int
    tasks: list[TaskItem]


class TaskCompleteRequest(BaseModel):
    telegram_chat_id: int
    task_id: int


class TaskCompleteResponse(BaseModel):
    user_id: int
    task_id: int
    completed: bool
    message: str


class TaskDeleteRequest(BaseModel):
    telegram_chat_id: int
    task_id: int


class TaskDeleteResponse(BaseModel):
    user_id: int
    task_id: int
    deleted: bool
    message: str


@router.post("", response_model=TaskCreateResponse)
async def save_task(request: TaskCreateRequest) -> TaskCreateResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        try:
            task = await create_task(
                session=session,
                user_id=user.id,
                title=request.title,
                due_date=request.due_date,
                source=request.source,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        await session.commit()

        return TaskCreateResponse(
            task_id=task.id,
            user_id=user.id,
            title=task.title,
            due_date=task.due_date,
            status=task.status,
        )


@router.post("/list", response_model=TaskListResponse)
async def list_tasks(request: TaskListRequest) -> TaskListResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        tasks = await list_user_tasks(
            session=session,
            user_id=user.id,
            status=request.status,
            limit=request.limit,
        )

        return TaskListResponse(
            user_id=user.id,
            tasks=[
                TaskItem(
                    id=task.id,
                    title=task.title,
                    due_date=task.due_date,
                    status=task.status,
                    source=task.source,
                )
                for task in tasks
            ],
        )


@router.post("/complete", response_model=TaskCompleteResponse)
async def complete_task(request: TaskCompleteRequest) -> TaskCompleteResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        completed = await complete_user_task(
            session=session,
            user_id=user.id,
            task_id=request.task_id,
        )

        await session.commit()

        if not completed:
            return TaskCompleteResponse(
                user_id=user.id,
                task_id=request.task_id,
                completed=False,
                message="No pending task was found for this user.",
            )

        return TaskCompleteResponse(
            user_id=user.id,
            task_id=request.task_id,
            completed=True,
            message="Task marked as completed.",
        )


@router.post("/delete", response_model=TaskDeleteResponse)
async def delete_task(request: TaskDeleteRequest) -> TaskDeleteResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        deleted = await delete_user_task(
            session=session,
            user_id=user.id,
            task_id=request.task_id,
        )

        await session.commit()

        if not deleted:
            return TaskDeleteResponse(
                user_id=user.id,
                task_id=request.task_id,
                deleted=False,
                message="No pending task was found for this user.",
            )

        return TaskDeleteResponse(
            user_id=user.id,
            task_id=request.task_id,
            deleted=True,
            message="Task deleted.",
        )
