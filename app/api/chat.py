from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.database import AsyncSessionLocal
from app.core.security import caller_is_trusted
from app.services.agent_service import run_agent
from app.services.chat_history_service import save_chat_message
from app.services.llm_client import generate_chat_response
from app.services.user_service import get_or_create_telegram_user

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    telegram_chat_id: int | None = None
    telegram_username: str | None = None
    telegram_first_name: str | None = None
    telegram_last_name: str | None = None
    source: str = "api"


class ChatResponse(BaseModel):
    response: str
    user_id: int | None = None
    source: str


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    caller_trusted: bool = Depends(caller_is_trusted),
) -> ChatResponse:
    # This route stays public so the browser chat UI works, but naming a
    # telegram_chat_id reads and writes that user's stored history and
    # memories, so it requires the shared secret.
    if request.telegram_chat_id is not None and not caller_trusted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "telegram_chat_id requires a valid X-API-Key header."
            ),
        )

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

            agent_result = await run_agent(
                session=session,
                user_id=user.id,
                user_message=request.message,
            )

            assistant_response = agent_result["final_response"]

            await save_chat_message(
                session=session,
                user_id=user.id,
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

    assistant_response = await generate_chat_response(
        user_message=request.message,
    )

    return ChatResponse(
        response=assistant_response,
        user_id=user_id,
        source=request.source,
    )