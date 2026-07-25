from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter()

@router.post("/chat/stream")
def chat_stream(request: ChatRequest):
    """
    流式问答接口
    返回 JSON Lines 格式的数据流
    """
    return StreamingResponse(
        ChatService.chat_stream(request.question, request.top_k),
        media_type="application/x-ndjson"
    )
