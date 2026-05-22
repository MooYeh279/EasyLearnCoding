import json
import re
import uuid
import asyncio
from sqlalchemy.orm import Session
from models import Topic, TopicOutline, Section, TopicStatus
from logger import get_logger
from config import AI_MAX_CONCURRENCY, CELL_ID_LENGTH

logger = get_logger("outline")


# Languages that produce runnable code cells (not display-only blocks)
_CODE_LANGUAGES = {"python", "javascript", "typescript", "bash", "shell", "c", "cpp", "cmd", "powershell", "bat", "ps1"}

def _markdown_to_cells(md: str, default_language: str = "python") -> str:
    """Convert AI-generated Markdown into a JSON cell array for notebook rendering.

    Rules:
    - Real language tag (python, js, c, etc.)  → runnable code cell
    - ``txt`` tag or bare ``` (no tag) → plaintext code cell (display, not runnable)
    - Unrecognized language → plaintext code cell
    - Text outside code fences → markdown cells
    """
    cells = []

    # Split on lines that are exactly ``` (opening or closing fence)
    blocks = re.split(r'^```', md, flags=re.MULTILINE)

    # blocks[0] = text before first ``` (always markdown)
    # blocks[1] = optional-lang\\n code after opening ```
    # blocks[2] = text after closing ``` (markdown)
    # blocks[3] = optional-lang\\n code after next opening ```
    # ... alternating markdown (even) / code (odd)
    for i, block in enumerate(blocks):
        if not block.strip():
            continue
        if i % 2 == 0:
            cells.append({
                "id": uuid.uuid4().hex[:CELL_ID_LENGTH],
                "type": "markdown",
                "content": block.strip(),
            })
        else:
            # First line is the language tag, rest is code
            first_newline = block.find("\n")
            if first_newline == -1:
                lang = block.strip()
                code = ""
            else:
                lang = block[:first_newline].strip()
                code = block[first_newline + 1:].strip()

            if not code:
                continue

            # Determine language: recognized → runnable, anything else → plaintext
            cell_lang = lang if lang.lower() in _CODE_LANGUAGES else "txt"

            cells.append({
                "id": uuid.uuid4().hex[:CELL_ID_LENGTH],
                "type": "code",
                "language": cell_lang,
                "code": code,
                "output": None,
            })

    return json.dumps(cells, ensure_ascii=False)


def save_outline(db: Session, topic: Topic, outline_data: dict, feedback: str = None):
    existing = db.query(TopicOutline).filter(TopicOutline.topic_id == topic.id).first()
    history = []
    if existing and existing.sections_json:
        history = (existing.feedback_history or []).copy()
        history.append({
            "previous_outline": existing.sections_json,
        })
    if feedback:
        if history:
            history[-1]["feedback"] = feedback

    if existing:
        existing.sections_json = outline_data
        existing.feedback_history = history
        saved = existing
    else:
        saved = TopicOutline(
            topic_id=topic.id,
            sections_json=outline_data,
            feedback_history=history,
        )
        db.add(saved)

    topic.status = TopicStatus.outline_ready
    db.commit()
    db.refresh(saved)
    return saved


def generate_content_concurrent(db: Session, topic: Topic, language_name: str,
                                 content_language: str = "zh", max_concurrency: int = AI_MAX_CONCURRENCY):
    from models import Lesson as LessonModel, LessonType
    from services.ai_service import generate_lesson_async

    topic.status = TopicStatus.generating_content
    topic.generation_progress = {"current": 0, "total": 0, "current_section": "", "current_lesson": ""}
    db.commit()

    topic_title = topic.title
    topic_id = topic.id

    try:
        outline = db.query(TopicOutline).filter(TopicOutline.topic_id == topic.id).first()
        if not outline:
            raise ValueError("No outline found for this topic")

        sections_data = outline.sections_json["sections"]

        # Build maps of existing DB state
        existing_sec_by_title: dict[str, Section] = {}
        for sec in topic.sections:
            existing_sec_by_title[sec.title] = sec

        outline_sec_titles = {s["title"] for s in sections_data}

        lesson_map: list[dict] = []

        # Sync: create/reuse sections and lessons from outline
        for sec_idx, sec_data in enumerate(sections_data):
            sec_title = sec_data["title"]

            if sec_title in existing_sec_by_title:
                section = existing_sec_by_title[sec_title]
                section.order = sec_idx
            else:
                section = Section(
                    topic_id=topic.id,
                    title=sec_title,
                    order=sec_idx,
                )
                db.add(section)
                db.commit()

            # Build map of existing lessons for this section
            # Re-query to get current state
            existing_les_by_title: dict[str, LessonModel] = {}
            for les in section.lessons:
                existing_les_by_title[les.title] = les

            outline_les_titles = {l["title"] for l in sec_data.get("lessons", [])}

            # Remove lessons no longer in outline
            for les in section.lessons:
                if les.title not in outline_les_titles:
                    db.delete(les)
            db.commit()

            # Create/reuse lessons
            for les_idx, les_data in enumerate(sec_data.get("lessons", [])):
                les_title = les_data["title"]

                if les_title in existing_les_by_title:
                    lesson = existing_les_by_title[les_title]
                    lesson.order = les_idx
                    # Only generate if content is empty or failed
                    needs_gen = not lesson.content or not lesson.content.startswith('[{"id":')
                    if needs_gen:
                        lesson_map.append({
                            "section_title": sec_title,
                            "lesson_title": les_title,
                            "lesson_id": lesson.id,
                        })
                else:
                    lesson = LessonModel(
                        section_id=section.id,
                        title=les_title,
                        order=les_idx,
                        content="",
                        lesson_type=LessonType.concept,
                    )
                    db.add(lesson)
                    db.commit()
                    lesson_map.append({
                        "section_title": sec_title,
                        "lesson_title": les_title,
                        "lesson_id": lesson.id,
                    })

        # Remove sections no longer in outline
        for sec in topic.sections:
            if sec.title not in outline_sec_titles:
                db.delete(sec)
        db.commit()

        total = len(lesson_map)
        topic.generation_progress = {"current": 0, "total": total, "current_section": "", "current_lesson": ""}
        db.commit()

        if total == 0:
            topic.status = TopicStatus.content_ready
            topic.generation_progress = None
            db.commit()
            return

        async def run_async():
            sem = asyncio.Semaphore(max_concurrency)

            async def generate_one(task):
                async with sem:
                    try:
                        content = await generate_lesson_async(
                            topic_title=topic_title,
                            language_name=language_name,
                            section_title=task["section_title"],
                            lesson_title=task["lesson_title"],
                            content_language=content_language,
                        )
                        return {**task, "content": content, "error": None}
                    except Exception as e:
                        logger.exception("Lesson generation failed: %s/%s",
                                         task["section_title"], task["lesson_title"])
                        return {**task, "content": f"[Generation failed: {e}]", "error": str(e)}

            tasks = [asyncio.create_task(generate_one(t)) for t in lesson_map]

            completed = 0
            for coro in asyncio.as_completed(tasks):
                result = await coro
                completed += 1

                lesson = db.query(LessonModel).filter(LessonModel.id == result["lesson_id"]).first()
                if lesson:
                    lesson.content = _markdown_to_cells(result["content"], language_name)

                topic_progress = db.query(Topic).filter(Topic.id == topic_id).first()
                if topic_progress:
                    topic_progress.generation_progress = {
                        "current": completed,
                        "total": total,
                        "current_section": result["section_title"],
                        "current_lesson": result["lesson_title"],
                    }
                db.commit()

        try:
            asyncio.run(run_async())
        except Exception:
            logger.exception("Content generation aborted")
            topic = db.query(Topic).filter(Topic.id == topic_id).first()
            if topic:
                topic.status = TopicStatus.outline_ready
                topic.generation_progress = None
            db.commit()
            return

        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if topic:
            topic.status = TopicStatus.content_ready
            topic.generation_progress = None
        db.commit()
    except Exception:
        logger.exception("Content generation setup failed: topic_id=%s", topic_id)
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if topic:
            topic.status = TopicStatus.outline_ready
            topic.generation_progress = None
        db.commit()
