from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import AsyncSessionLocal
from app.services.agent_tools import (
    AGENT_TOOL_SCHEMAS,
    execute_agent_tool,
    get_agent_tool_names,
)
from app.services.user_service import get_or_create_telegram_user

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentToolListResponse(BaseModel):
    tools: list[str]
    schemas: list[dict[str, Any]]


class AgentToolTestRequest(BaseModel):
    telegram_chat_id: int
    tool_name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentToolTestResponse(BaseModel):
    user_id: int
    tool_name: str
    result: dict[str, Any]


@router.get("/tools", response_model=AgentToolListResponse)
async def list_agent_tools() -> AgentToolListResponse:
    return AgentToolListResponse(
        tools=get_agent_tool_names(),
        schemas=AGENT_TOOL_SCHEMAS,
    )


@router.post("/test-tool", response_model=AgentToolTestResponse)
async def test_agent_tool(
    request: AgentToolTestRequest,
) -> AgentToolTestResponse:
    async with AsyncSessionLocal() as session:
        user = await get_or_create_telegram_user(
            session=session,
            telegram_chat_id=request.telegram_chat_id,
        )

        try:
            result = await execute_agent_tool(
                session=session,
                user_id=user.id,
                tool_name=request.tool_name,
                arguments=request.arguments,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        await session.commit()

        return AgentToolTestResponse(
            user_id=user.id,
            tool_name=request.tool_name,
            result=result,
        )