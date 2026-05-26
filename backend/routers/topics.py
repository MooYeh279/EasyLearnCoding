import asyncio
import json
import re
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from logger import get_logger
from sqlalchemy.orm import Session, selectinload
from database import get_db, SessionLocal
from models import Course, Topic, TopicStatus, Section, TopicOutline, Lesson, LessonType
from pydantic import BaseModel
from services.ai_service import generate_outline_stream_async, generate_lesson_stream_async
from services.outline_service import save_outline, _markdown_to_cells
from services.tools import is_web_search_enabled

logger = get_logger("topics")

router = APIRouter(prefix="/api", tags=["topics"])

# Track topic IDs with an active outline generation SSE connection
_active_outline_streams: set[int] = set()


def _repair_json(text: str) -> str:
    """Fix unescaped double quotes inside JSON string values.

    AI sometimes writes Chinese text like 拥有"记忆" inside JSON strings
    where the inner " are not escaped, breaking json.loads. This tracks
    string state and escapes quotes that don't appear to be structural.
    """
    result: list[str] = []
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            result.append(ch)
            continue
        if ch == "\\":
            escape = True
            result.append(ch)
            continue
        if ch == '"':
            if in_string:
                j = i + 1
                while j < len(text) and text[j] in " \t\r\n":
                    j += 1
                if j < len(text) and text[j] in ",:}]":
                    in_string = False
                else:
                    result.append("\\")
            else:
                in_string = True
        result.append(ch)
    return "".join(result)


class TopicCreate(BaseModel):
    title: str


class OutlineGenerateRequest(BaseModel):
    topic_title: str
    feedback: str | None = None
    content_language: str = "zh"


class ContentGenerateRequest(BaseModel):
    content_language: str = "zh"


class OutlineUpdateRequest(BaseModel):
    sections: list[dict]


class LessonUpdateRequest(BaseModel):
    content: str


def _reset_outline_status(topic_id: int):
    """Reset a stuck generating_outline topic back to draft or outline_ready."""
    reset_db = SessionLocal()
    try:
        tp = reset_db.query(Topic).filter(Topic.id == topic_id).first()
        if tp and tp.status == TopicStatus.generating_outline:
            has_outline = reset_db.query(TopicOutline).filter(TopicOutline.topic_id == topic_id).first()
            tp.status = TopicStatus.outline_ready if has_outline else TopicStatus.draft
            reset_db.commit()
            logger.info("Reset stuck outline generation: topic_id=%s -> %s", topic_id, tp.status.value)
    finally:
        reset_db.close()


def _reset_content_to_outline(topic_id: int):
    """Reset a topic from generating_content back to outline_ready so failed
    lessons can be re-generated."""
    reset_db = SessionLocal()
    try:
        tp = reset_db.query(Topic).filter(Topic.id == topic_id).first()
        if tp and tp.status == TopicStatus.generating_content:
            tp.status = TopicStatus.outline_ready
            tp.generation_progress = None
            reset_db.commit()
            logger.info("Topic %s reset to outline_ready due to generation failures", topic_id)
    finally:
        reset_db.close()


@router.post("/courses/{course_id}/topics", status_code=201)
def create_topic(course_id: int, body: TopicCreate, db: Session = Depends(get_db)):
    topic = Topic(course_id=course_id, title=body.title, status=TopicStatus.draft)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


@router.get("/topics/{topic_id}")
def get_topic(topic_id: int, brief: bool = False, db: Session = Depends(get_db)):
    topic = (
        db.query(Topic)
        .options(selectinload(Topic.sections).selectinload(Section.lessons))
        .options(selectinload(Topic.course).selectinload(Course.language))
        .filter(Topic.id == topic_id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Topic not found")

    # Auto-recover: if generating_outline but no active SSE stream, reset status
    if brief and topic.status == TopicStatus.generating_outline and topic_id not in _active_outline_streams:
        has_outline = db.query(TopicOutline).filter(TopicOutline.topic_id == topic_id).first()
        topic.status = TopicStatus.outline_ready if has_outline else TopicStatus.draft
        db.commit()
        logger.info("Auto-recovered stuck outline on poll: topic_id=%s -> %s", topic_id, topic.status.value)

    if not brief:
        return topic

    return {
        "id": topic.id,
        "course_id": topic.course_id,
        "title": topic.title,
        "status": topic.status.value,
        "generation_progress": topic.generation_progress,
        "created_at": topic.created_at.isoformat() if topic.created_at else None,
        "course": {"id": topic.course.id, "language": {"id": topic.course.language.id, "name": topic.course.language.name, "display_name": topic.course.language.display_name}},
        "sections": [
            {
                "id": sec.id,
                "title": sec.title,
                "order": sec.order,
                "lessons": [
                    {
                        "id": les.id,
                        "title": les.title,
                        "order": les.order,
                        "has_content": bool(les.content),
                    }
                    for les in sorted(sec.lessons, key=lambda l: l.order)
                ],
            }
            for sec in sorted(topic.sections, key=lambda s: s.order)
        ],
    }


@router.delete("/topics/{topic_id}", status_code=204)
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Topic not found")
    db.delete(topic)
    db.commit()



@router.get("/topics/{topic_id}/outline")
def get_outline(topic_id: int, db: Session = Depends(get_db)):
    outline = db.query(TopicOutline).filter(TopicOutline.topic_id == topic_id).first()
    if not outline:
        return {"sections": []}
    sections_data = outline.sections_json
    if isinstance(sections_data, dict):
        sections = sections_data.get("sections", [])
    else:
        sections = []
    return {
        "id": outline.id,
        "topic_id": outline.topic_id,
        "sections": sections,
    }


@router.put("/topics/{topic_id}/outline")
def update_outline(topic_id: int, body: OutlineUpdateRequest, db: Session = Depends(get_db)):
    outline = db.query(TopicOutline).filter(TopicOutline.topic_id == topic_id).first()
    if not outline:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="No outline found")

    outline.sections_json = {"sections": body.sections}
    db.commit()
    return {"sections": body.sections}


@router.put("/lessons/{lesson_id}")
def update_lesson(lesson_id: int, body: LessonUpdateRequest, db: Session = Depends(get_db)):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Lesson not found")
    lesson.content = body.content
    db.commit()
    return {"id": lesson.id, "title": lesson.title, "content": lesson.content}


@router.post("/topics/{topic_id}/generate-outline-stream")
async def generate_outline_stream(topic_id: int, body: OutlineGenerateRequest, db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Topic not found")
    language_name = topic.course.language.name

    previous = None
    existing_outline = db.query(TopicOutline).filter(TopicOutline.topic_id == topic_id).first()
    if existing_outline and existing_outline.sections_json:
        previous = existing_outline.sections_json

    topic.status = TopicStatus.generating_outline
    db.commit()

    enable_tools = is_web_search_enabled()
    _active_outline_streams.add(topic_id)

    async def generate():
        outline_saved = False
        try:
            yield f"event: agent_start\ndata: {json.dumps({'type': 'agent_start', 'message': 'Starting outline generation...'})}\n\n"

            outline_text = ""
            try:
                async for event in generate_outline_stream_async(
                    topic_title=body.topic_title,
                    language_name=language_name,
                    content_language=body.content_language,
                    previous_outline=previous,
                    feedback=body.feedback,
                    enable_tools=enable_tools,
                ):
                    yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                    if event["type"] == "agent_done":
                        outline_text = event["text"]
                    elif event["type"] == "agent_error":
                        _reset_outline_status(topic_id)
                        return
            except Exception:
                logger.exception("Outline stream generation failed: topic_id=%s", topic_id)
                yield f"event: agent_error\ndata: {json.dumps({'type': 'agent_error', 'error': 'AI generation failed'})}\n\n"
                _reset_outline_status(topic_id)
                return

            text = outline_text.strip()
            # Strip markdown code fences
            m = re.search(r"```(?:json)?[^\n]*\n(.*?)```", text, re.DOTALL)
            if m:
                text = m.group(1).strip()
            elif text.startswith("```"):
                first_nl = text.find("\n")
                if first_nl != -1:
                    text = text[first_nl + 1:]
                if text.rstrip().endswith("```"):
                    text = text.rstrip()[:-3].strip()
            # Fallback: find JSON object boundaries
            if text and text[0] == "{":
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    text = text[start:end + 1]
            if not text or text[0] not in "{[":
                logger.error("Generated content is not JSON: preview=%s", outline_text[:200])
                yield f"event: agent_error\ndata: {json.dumps({'type': 'agent_error', 'error': 'AI returned invalid format, please retry'})}\n\n"
                _reset_outline_status(topic_id)
                return
            try:
                outline_data = json.loads(text)
            except json.JSONDecodeError:
                text = _repair_json(text)
                try:
                    outline_data = json.loads(text)
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse outline JSON: error=%s text_preview=%s", e, outline_text[:300])
                    yield f"event: agent_error\ndata: {json.dumps({'type': 'agent_error', 'error': 'Failed to parse generated outline'})}\n\n"
                    _reset_outline_status(topic_id)
                    return

            save_outline(db, topic_id, outline_data, body.feedback)
            outline_saved = True
            yield f"event: outline_saved\ndata: {json.dumps({'type': 'outline_saved', 'topic_id': topic_id, 'sections': outline_data.get('sections', [])})}\n\n"
        finally:
            _active_outline_streams.discard(topic_id)
            if not outline_saved:
                _reset_outline_status(topic_id)

    return StreamingResponse(generate(), media_type="text/event-stream")


def _sync_sections_and_lessons(db: Session, topic: Topic, sections_data: list[dict]) -> list[dict]:
    """Sync sections and lessons with outline data. Returns list of lesson tasks to generate."""
    existing_sec_by_title = {sec.title: sec for sec in topic.sections}
    outline_sec_titles = {s["title"] for s in sections_data}
    lesson_tasks: list[dict] = []

    for sec_idx, sec_data in enumerate(sections_data):
        sec_title = sec_data["title"]
        if sec_title in existing_sec_by_title:
            section = existing_sec_by_title[sec_title]
            section.order = sec_idx
        else:
            section = Section(topic_id=topic.id, title=sec_title, order=sec_idx)
            db.add(section)
            db.commit()

        existing_les_by_title = {les.title: les for les in section.lessons}
        outline_les_titles = {l["title"] for l in sec_data.get("lessons", [])}

        for les in section.lessons:
            if les.title not in outline_les_titles:
                db.delete(les)
        db.commit()

        for les_idx, les_data in enumerate(sec_data.get("lessons", [])):
            les_title = les_data["title"]
            if les_title in existing_les_by_title:
                lesson = existing_les_by_title[les_title]
                lesson.order = les_idx
                if not lesson.content or not lesson.content.startswith('[{"id":'):
                    lesson_tasks.append({
                        "section_title": sec_title,
                        "lesson_title": les_title,
                        "lesson_id": lesson.id,
                    })
            else:
                lesson = Lesson(
                    section_id=section.id, title=les_title, order=les_idx,
                    content="", lesson_type=LessonType.concept,
                )
                db.add(lesson)
                db.commit()
                lesson_tasks.append({
                    "section_title": sec_title,
                    "lesson_title": les_title,
                    "lesson_id": lesson.id,
                })

    for sec in topic.sections:
        if sec.title not in outline_sec_titles:
            db.delete(sec)
    db.commit()

    return lesson_tasks


def _save_lesson(lesson_id: int, full_text: str, language_name: str):
    """Persist generated lesson content to database."""
    db = SessionLocal()
    try:
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if lesson:
            lesson.content = _markdown_to_cells(full_text, language_name)
        db.commit()
    finally:
        db.close()


def _update_progress(topic_id: int, completed: int, total: int, task: dict):
    """Update generation progress in database."""
    db = SessionLocal()
    try:
        tp = db.query(Topic).filter(Topic.id == topic_id).first()
        if tp:
            tp.generation_progress = {
                "current": completed,
                "total": total,
                "current_section": task["section_title"],
                "current_lesson": task["lesson_title"],
            }
        db.commit()
    finally:
        db.close()


def _mark_content_ready(topic_id: int):
    """Mark topic as content_ready in database."""
    db = SessionLocal()
    try:
        t = db.query(Topic).filter(Topic.id == topic_id).first()
        if t:
            t.status = TopicStatus.content_ready
            t.generation_progress = None
        db.commit()
    finally:
        db.close()


async def _run_lesson_task(
    task: dict,
    topic_title: str,
    language_name: str,
    content_language: str,
    sem: asyncio.Semaphore,
    event_queue: asyncio.Queue,
    progress: dict,
    total: int,
    topic_id: int,
    enable_tools: bool = True,
):
    """Generate content for one lesson and push events to the shared queue."""
    async with sem:
        full_text = ""
        failed = False
        try:
            async for event in generate_lesson_stream_async(
                topic_title=topic_title,
                language_name=language_name,
                section_title=task["section_title"],
                lesson_title=task["lesson_title"],
                content_language=content_language,
                enable_tools=enable_tools,
            ):
                if event["type"] == "agent_done":
                    full_text = event["text"]
                elif event["type"] == "agent_error":
                    logger.error(
                        "Lesson agent_error: lesson_id=%s title=%s error=%s",
                        task["lesson_id"], task["lesson_title"], event.get("error"),
                    )
                    failed = True
                    await event_queue.put({
                        **event,
                        "lesson_id": task["lesson_id"],
                        "lesson_title": task["lesson_title"],
                    })
                    break
                # generate_lesson_stream_async only yields agent_done/agent_error —
                # frontend only needs progress + final results for content generation
        except Exception:
            logger.exception("Lesson generation failed: lesson_id=%s title=%s", task["lesson_id"], task["lesson_title"])
            failed = True
            await event_queue.put({
                "type": "agent_error",
                "lesson_id": task["lesson_id"],
                "lesson_title": task["lesson_title"],
                "error": f"Unexpected error generating {task['lesson_title']}",
            })

        if not failed:
            _save_lesson(task["lesson_id"], full_text, language_name)
        else:
            progress["failed_count"] += 1

        progress["completed"] += 1
        await event_queue.put({
            "type": "progress",
            "current": progress["completed"],
            "total": total,
            "current_section": task["section_title"],
            "current_lesson": task["lesson_title"],
            "lesson_id": task["lesson_id"],
            "failed": failed,
        })

        _update_progress(topic_id, progress["completed"], total, task)


def _prepare_content_generation(topic_id: int) -> tuple:
    """Validate topic state, sync outline, and set generating status.
    Returns (topic_title, language_name, lesson_tasks, total)."""
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Topic not found")
        if topic.status == TopicStatus.generating_content:
            logger.warning("generate-content-stream restarting after stuck generation: topic_id=%s", topic_id)
            topic.status = TopicStatus.outline_ready
            topic.generation_progress = None
            db.commit()
        if topic.status not in (TopicStatus.outline_ready, TopicStatus.content_ready):
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Outline must be ready before generating content")
        language_name = topic.course.language.name
        topic_title = topic.title
        outline = db.query(TopicOutline).filter(TopicOutline.topic_id == topic_id).first()
        if not outline:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="No outline found")
        lesson_tasks = _sync_sections_and_lessons(db, topic, outline.sections_json["sections"])
        total = len(lesson_tasks)
        topic.status = TopicStatus.generating_content
        topic.generation_progress = {"current": 0, "total": total, "current_section": "", "current_lesson": ""}
        db.commit()
        return topic_title, language_name, lesson_tasks, total
    finally:
        db.close()


@router.post("/topics/{topic_id}/generate-content-stream")
async def generate_content_stream(topic_id: int, body: ContentGenerateRequest = ContentGenerateRequest()):
    topic_title, language_name, lesson_tasks, total = _prepare_content_generation(topic_id)
    enable_tools = is_web_search_enabled()

    async def generate():
        from config import AI_MAX_CONCURRENCY

        yield f"event: agent_start\ndata: {json.dumps({'type': 'agent_start', 'message': 'Starting content generation...', 'total': total})}\n\n"

        if total == 0:
            _mark_content_ready(topic_id)
            yield f"event: all_done\ndata: {json.dumps({'type': 'all_done', 'topic_id': topic_id})}\n\n"
            return

        sem = asyncio.Semaphore(AI_MAX_CONCURRENCY)
        progress = {"completed": 0, "failed_count": 0}
        event_queue: asyncio.Queue = asyncio.Queue()

        async def producer():
            await asyncio.gather(*(
                _run_lesson_task(t, topic_title, language_name, body.content_language, sem, event_queue, progress, total, topic_id, enable_tools)
                for t in lesson_tasks
            ), return_exceptions=True)
            if progress["failed_count"] > 0:
                _reset_content_to_outline(topic_id)
            else:
                _mark_content_ready(topic_id)
            await event_queue.put(None)

        producer_task = asyncio.create_task(producer())

        try:
            while True:
                item = await event_queue.get()
                if item is None:
                    break
                yield f"event: {item.get('type', 'message')}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"

            await producer_task
            yield f"event: all_done\ndata: {json.dumps({'type': 'all_done', 'topic_id': topic_id, 'failed_count': progress['failed_count']})}\n\n"
        except (GeneratorExit, asyncio.CancelledError, ConnectionError):
            # Client disconnected — producer continues in background,
            # _mark_content_ready is called by producer when all lessons complete.
            pass

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/lessons/{lesson_id}/regenerate")
async def regenerate_lesson(lesson_id: int, db: Session = Depends(get_db)):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Lesson not found")

    section = lesson.section
    topic = section.topic
    language_name = topic.course.language.name

    try:
        full_text = ""
        async for event in generate_lesson_stream_async(
            topic_title=topic.title,
            language_name=language_name,
            section_title=section.title,
            lesson_title=lesson.title,
        ):
            if event["type"] == "agent_done":
                full_text = event["text"]
            elif event["type"] == "agent_error":
                raise HTTPException(
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                    detail=event.get("error", "Generation failed"),
                )

        lesson.content = _markdown_to_cells(full_text, language_name)
        db.commit()
        return {"id": lesson.id, "title": lesson.title, "content": lesson.content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))
