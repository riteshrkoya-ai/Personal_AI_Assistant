from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.services.llm_client import generate_chat_response

router = APIRouter(tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    response_text = await generate_chat_response(request.message)
    return ChatResponse(response=response_text)