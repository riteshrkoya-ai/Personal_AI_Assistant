from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import AsyncSessionLocal
from app.services.memory_service import (
    create_memory,
    delete_user_memory,
    list_user_memories,
    search_user_memories,
)
from app.services.user_service import get_or_create_telegram_user

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryCreateRequest(BaseModel):
    telegram_chat_id: int
    content: str = Field(..., min_length=1)
    source: str = "telegram"


class MemoryCreateResponse(BaseModel):
    memory_id: int
    user_id: int
    content: str
    source: str


class MemorySearchRequest(BaseModel):
    telegram_chat_id: int
    query: str = Field(..., min_length=1)
    top_k: int = 5


class MemoryListRequest(BaseModel):
    telegram_chat_id: int
    limit: int = 20


class MemoryDeleteRequest(BaseModel):
    telegram_chat_id: int
    memory_id: int


class MemoryItem(BaseModel):
    id: int
    content: str
    source: str


class MemoryListResponse(BaseModel):
    user_id: int
    memories: list[MemoryItem]


class MemoryDeleteResponse(BaseModel):
    user_id: int
    memory_id: int
    deleted: bool
    message: str


@router.post("", response_model=MemoryCreateResponse)
async def save_memory(request: MemoryCreateRequest) -> MemoryCreateResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        try:
            memory = await create_memory(
                session=session,
                user_id=user.id,
                content=request.content,
                source=request.source,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        await session.commit()

        return MemoryCreateResponse(
            memory_id=memory.id,
            user_id=user.id,
            content=memory.content,
            source=memory.source,
        )


@router.post("/search", response_model=MemoryListResponse)
async def search_memory(request: MemorySearchRequest) -> MemoryListResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        memories = await search_user_memories(
            session=session,
            user_id=user.id,
            query=request.query,
            top_k=request.top_k,
        )

        return MemoryListResponse(
            user_id=user.id,
            memories=[
                MemoryItem(
                    id=memory.id,
                    content=memory.content,
                    source=memory.source,
                )
                for memory in memories
            ],
        )


@router.post("/list", response_model=MemoryListResponse)
async def list_memories(request: MemoryListRequest) -> MemoryListResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        memories = await list_user_memories(
            session=session,
            user_id=user.id,
            limit=request.limit,
        )

        return MemoryListResponse(
            user_id=user.id,
            memories=[
                MemoryItem(
                    id=memory.id,
                    content=memory.content,
                    source=memory.source,
                )
                for memory in memories
            ],
        )


@router.post("/delete", response_model=MemoryDeleteResponse)
async def delete_memory(request: MemoryDeleteRequest) -> MemoryDeleteResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        deleted = await delete_user_memory(
            session=session,
            user_id=user.id,
            memory_id=request.memory_id,
        )

        await session.commit()

        if not deleted:
            return MemoryDeleteResponse(
                user_id=user.id,
                memory_id=request.memory_id,
                deleted=False,
                message="No matching memory was found for this user.",
            )

        return MemoryDeleteResponse(
            user_id=user.id,
            memory_id=request.memory_id,
            deleted=True,
            message="Memory deleted successfully.",
        )