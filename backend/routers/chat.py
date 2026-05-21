"""Chat endpoint for AI learning assistant (SSE streaming)."""
import json
from http import HTTPStatus

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import PROMPTS_DIR, CHAT_CONTENT_MAX_CHARS, CHAT_HISTORY_MAX, CHAT_TEMPERATURE
from database import SessionLocal
from services.ai_service import get_provider, get_model
from models import Lesson

router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    lesson_id: int
    history: list[ChatMessage] = []


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


@router.post("/chat")
async def chat(body: ChatRequest):
    """Stream AI chat response via SSE."""
    db = SessionLocal()
    try:
        lesson = db.query(Lesson).filter(Lesson.id == body.lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Lesson not found")
        lesson_content = lesson.content or ""
        lesson_title = lesson.title
    finally:
        db.close()

    prompt_template = _load_prompt("chat_assistant.txt")
    system_prompt = prompt_template.format(
        lesson_title=lesson_title,
        lesson_content=lesson_content[:CHAT_CONTENT_MAX_CHARS],
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in body.history[-CHAT_HISTORY_MAX:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": body.message})

    async def generate():
        try:
            stream = get_provider().chat_completion_stream_async(
                model=get_model(),
                messages=messages,
                temperature=CHAT_TEMPERATURE,
            )
            full_text = ""
            async for chunk in stream:
                full_text += chunk
                yield f"event: chunk\ndata: {json.dumps({'text': chunk})}\n\n"
            yield f"event: done\ndata: {json.dumps({'text': full_text})}\n\n"
        except Exception as e:
            error_msg = f"AI request failed: {str(e)}"
            yield f"event: error\ndata: {json.dumps({'text': error_msg})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
