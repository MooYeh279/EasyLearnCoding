import asyncio
import threading
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException
from logger import get_logger
from sqlalchemy.orm import Session, selectinload
from database import get_db, SessionLocal
from models import Course, Topic, TopicStatus, Section, TopicOutline, Lesson
from pydantic import BaseModel
from services.ai_service import generate_outline_async
from services.ai_service import generate_lesson_async
from services.outline_service import save_outline, generate_content_concurrent, _markdown_to_cells

logger = get_logger("topics")

router = APIRouter(prefix="/api", tags=["topics"])


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


def _run_content_generation(topic_id: int, content_language: str):
    """Run content generation in a background thread using asyncio for concurrent AI calls."""
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            return
        language_name = topic.course.language.name
        generate_content_concurrent(db, topic, language_name, content_language)
    finally:
        db.close()


@router.post("/courses/{course_id}/topics", status_code=201)
def create_topic(course_id: int, body: TopicCreate, db: Session = Depends(get_db)):
    topic = Topic(course_id=course_id, title=body.title, status=TopicStatus.draft)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


@router.get("/topics/{topic_id}")
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = (
        db.query(Topic)
        .options(selectinload(Topic.sections).selectinload(Section.lessons))
        .options(selectinload(Topic.course).selectinload(Course.language))
        .filter(Topic.id == topic_id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Topic not found")
    return topic


@router.delete("/topics/{topic_id}", status_code=204)
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Topic not found")
    db.delete(topic)
    db.commit()


@router.post("/topics/{topic_id}/generate-outline")
def generate_outline(topic_id: int, body: OutlineGenerateRequest, db: Session = Depends(get_db)):
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

    try:
        outline_data = asyncio.run(generate_outline_async(
            topic_title=body.topic_title,
            language_name=language_name,
            previous_outline=previous,
            feedback=body.feedback,
            content_language=body.content_language,
        ))
    except Exception:
        logger.exception("Outline generation failed: topic_id=%s", topic_id)
        topic.status = TopicStatus.outline_ready if previous else TopicStatus.draft
        topic.generation_progress = None
        db.commit()
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                           detail="AI generation failed. Please check your model configuration.")

    saved = save_outline(db, topic, outline_data, body.feedback)
    return {
        "id": saved.id,
        "topic_id": saved.topic_id,
        "sections": outline_data.get("sections", []),
    }


@router.post("/topics/{topic_id}/generate-content")
def generate_content(topic_id: int, body: ContentGenerateRequest = ContentGenerateRequest(), db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Topic not found")

    if topic.status not in (TopicStatus.outline_ready, TopicStatus.generating_content):
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Outline must be ready before generating content")

    language_name = topic.course.language.name
    generate_content_concurrent(db, topic, language_name, body.content_language)
    return {"status": "content_ready"}


@router.post("/topics/{topic_id}/generate-content-stream")
def generate_content_stream(topic_id: int, body: ContentGenerateRequest = ContentGenerateRequest()):
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
            logger.warning("generate-content-stream rejected: topic_id=%s status=%s (expected outline_ready or content_ready)", topic_id, topic.status)
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Outline must be ready before generating content")

        logger.info("generate-content-stream starting: topic_id=%s status=%s", topic_id, topic.status)

        topic.status = TopicStatus.generating_content
        topic.generation_progress = {"current": 0, "total": 0, "current_section": "", "current_lesson": ""}
        db.commit()
    finally:
        db.close()

    thread = threading.Thread(
        target=_run_content_generation,
        args=(topic_id, body.content_language),
        daemon=True,
    )
    thread.start()
    return {"status": "generation_started"}


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


@router.post("/lessons/{lesson_id}/regenerate")
def regenerate_lesson(lesson_id: int, db: Session = Depends(get_db)):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Lesson not found")

    section = lesson.section
    topic = section.topic
    language_name = topic.course.language.name

    try:
        content = asyncio.run(generate_lesson_async(
            topic_title=topic.title,
            language_name=language_name,
            section_title=section.title,
            lesson_title=lesson.title,
        ))
        lesson.content = _markdown_to_cells(content, language_name)
        db.commit()
        return {"id": lesson.id, "title": lesson.title, "content": lesson.content}
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))
