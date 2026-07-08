from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.database import AsyncSessionLocal
from app.services.chat_history_service import save_chat_message
from app.services.llm_client import generate_chat_response
from app.services.user_service import get_or_create_telegram_user

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    telegram_chat_id: int | None = None
    source: str = "api"


class ChatResponse(BaseModel):
    response: str
    user_id: int | None = None
    source: str


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    user_id: int | None = None

    async with AsyncSessionLocal() as session:
        if request.telegram_chat_id is not None:
            user = await get_or_create_telegram_user(
                session=session,
                telegram_chat_id=request.telegram_chat_id,
            )

            user_id = user.id

            await save_chat_message(
                session=session,
                user_id=user.id,
                role="user",
                content=request.message,
                source=request.source,
            )

            await session.commit()

    assistant_response = await generate_chat_response(request.message)

    if user_id is not None:
        async with AsyncSessionLocal() as session:
            await save_chat_message(
                session=session,
                user_id=user_id,
                role="assistant",
                content=assistant_response,
                source=request.source,
            )

            await session.commit()

    return ChatResponse(
        response=assistant_response,
        user_id=user_id,
        source=request.source,
    )