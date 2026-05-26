import json
from fastapi import APIRouter, Depends, HTTPException
from http import HTTPStatus
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import CODE_MAX_LENGTH
from database import get_db
from logger import get_logger
from models import Exercise, Section, Topic, Lesson
from services.ai_service import generate_exercise_async
from services.exercise_service import validate_exercise, run_exercise_code
from services.template_generator import generate_template_from_solution

logger = get_logger("exercises")
router = APIRouter(prefix="/api", tags=["exercises"])

MAX_GENERATION_ATTEMPTS = 3
MAX_STRUCTURE_RETRIES = 2

_regenerating: set[int] = set()


def _cells_to_text(content: str) -> str:
    """Extract readable markdown from JSON cell array stored in lesson.content."""
    if not content or not content.startswith("["):
        return content or ""
    try:
        cells = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content
    parts = []
    for cell in cells:
        if isinstance(cell, dict):
            cell_type = cell.get("type", "")
            if cell_type == "markdown":
                parts.append(cell.get("content", ""))
            elif cell_type == "code":
                lang = cell.get("language", "")
                code = cell.get("code", "")
                parts.append(f"```{lang}\n{code}\n```")
    return "\n\n".join(parts)


def _build_knowledge_summary(lessons, max_chars_per_lesson: int = 2000) -> str:
    """Build a knowledge description from lesson content."""
    parts = []
    for l in lessons:
        raw = (l.content or "").strip()
        text = _cells_to_text(raw) if raw else ""
        if text:
            preview = text[:max_chars_per_lesson]
            if len(text) > max_chars_per_lesson:
                preview += "..."
            parts.append(f"# {l.title}\n{preview}")
        else:
            parts.append(f"# {l.title} (no content yet)")
    return "\n\n".join(parts)


class RunExerciseRequest(BaseModel):
    code: str


def _ex_to_response(ex: Exercise) -> dict:
    return {
        "id": ex.id,
        "question": ex.question,
        "template": ex.template,
        "test_cases": ex.test_cases,
        "knowledge_tags": ex.knowledge_tags or [],
        "hints": ex.hints or [],
        "section_id": ex.section_id,
        "type": ex.type,
        "language": ex.language or "python",
        "declarations": ex.declarations or "",
        "regenerating": ex.id in _regenerating,
    }


async def _generate_validated_exercise(
    language_name: str,
    topic_title: str,
    section_title: str,
    knowledge_description: str,
    content_language: str = "zh",
) -> tuple:
    """Generate and validate an exercise with multi-layer retry.

    Returns (exercise: RawExerciseOutput, validation: ValidationResult, template: str).
    Raises HTTPException on exhaustion.
    """
    validation = None
    exercise = None
    structure_retries = 0

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        error_feedback = None
        if validation and not validation.valid:
            error_feedback = f"Layer {validation.layer}: {validation.error}"

        try:
            exercise = await generate_exercise_async(
                topic_title=topic_title,
                language_name=language_name,
                section_title=section_title,
                knowledge_description=knowledge_description,
                content_language=content_language,
                error_feedback=error_feedback,
            )
        except Exception as e:
            if structure_retries < MAX_STRUCTURE_RETRIES:
                structure_retries += 1
                logger.warning(
                    "Exercise structure parse failed (structure retry %d/%d): %s",
                    structure_retries, MAX_STRUCTURE_RETRIES, str(e)[:100],
                )
                continue
            logger.warning("Exercise generation failed: %s", e)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="AI generation failed",
            )

        validation = validate_exercise(language_name, exercise)

        if validation.valid:
            template = generate_template_from_solution(exercise.solution, language_name)
            return exercise, validation, template

        logger.warning(
            "Exercise validation FAILED at layer %s (attempt %d/%d): %s",
            validation.layer, attempt + 1, MAX_GENERATION_ATTEMPTS, validation.error[:100],
        )

    logger.warning(
        "Exercise validation FAILED after %d attempts: %s",
        MAX_GENERATION_ATTEMPTS, validation.error if validation else "unknown",
    )
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail={
            "message": "Generated exercise failed validation after retries",
            "validation_error": validation.error if validation else "",
            "validation_layer": validation.layer if validation else "",
        },
    )


@router.post("/sections/{section_id}/generate-exercise")
async def generate_section_exercise(section_id: int, db: Session = Depends(get_db)):
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Section not found")

    topic = db.query(Topic).filter(Topic.id == section.topic_id).first()
    if not topic or not topic.course:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Topic not found")

    language_name = topic.course.language.name if topic.course.language else "python"
    lessons = db.query(Lesson).filter(Lesson.section_id == section_id).all()
    knowledge_description = _build_knowledge_summary(lessons)

    exercise, validation, template = await _generate_validated_exercise(
        language_name=language_name,
        topic_title=topic.title,
        section_title=section.title,
        knowledge_description=knowledge_description,
    )

    test_cases_data = [tc.model_dump() for tc in exercise.test_cases]
    db_exercise = Exercise(
        section_id=section_id,
        type="section",
        language=language_name,
        question=exercise.question,
        template=template,
        test_cases=json.dumps(test_cases_data, ensure_ascii=False),
        solution=exercise.solution,
        declarations=exercise.declarations,
        knowledge_tags=exercise.knowledge_tags,
        hints=exercise.hints,
    )
    db.add(db_exercise)
    db.commit()
    db.refresh(db_exercise)
    return _ex_to_response(db_exercise)


@router.post("/topics/{topic_id}/generate-comprehensive-exercise")
async def generate_topic_exercise(topic_id: int, db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic or not topic.course:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Topic not found")

    language_name = topic.course.language.name if topic.course.language else "python"
    sections = db.query(Section).filter(Section.topic_id == topic_id).all()
    section_ids = [s.id for s in sections]
    lessons = db.query(Lesson).filter(Lesson.section_id.in_(section_ids)).all() if section_ids else []
    knowledge_description = _build_knowledge_summary(lessons, max_chars_per_lesson=500)

    exercise, validation, template = await _generate_validated_exercise(
        language_name=language_name,
        topic_title=topic.title,
        section_title=f"{topic.title} (Comprehensive)",
        knowledge_description=knowledge_description,
    )

    test_cases_data = [tc.model_dump() for tc in exercise.test_cases]
    db_exercise = Exercise(
        type="topic",
        topic_id=topic_id,
        language=language_name,
        question=exercise.question,
        template=template,
        test_cases=json.dumps(test_cases_data, ensure_ascii=False),
        solution=exercise.solution,
        declarations=exercise.declarations,
        knowledge_tags=exercise.knowledge_tags,
        hints=exercise.hints,
    )
    db.add(db_exercise)
    db.commit()
    db.refresh(db_exercise)
    return _ex_to_response(db_exercise)


@router.put("/exercises/{exercise_id}/code")
def save_exercise_code(exercise_id: int, req: RunExerciseRequest, db: Session = Depends(get_db)):
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Exercise not found")
    exercise.template = req.code
    db.commit()
    return {"ok": True}


@router.get("/exercises/{exercise_id}")
def get_exercise(exercise_id: int, db: Session = Depends(get_db)):
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Exercise not found")
    return _ex_to_response(exercise)


@router.post("/exercises/{exercise_id}/regenerate")
async def regenerate_exercise(exercise_id: int, db: Session = Depends(get_db)):
    """Regenerate an exercise in-place, keeping the same ID."""
    if exercise_id in _regenerating:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Exercise regeneration already in progress")

    existing = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not existing:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Exercise not found")

    _regenerating.add(exercise_id)
    try:
        # Derive context from the existing exercise's section/topic
        language_name = existing.language or "python"
        knowledge_description = ""
        topic_title = ""
        section_title = ""

        if existing.type == "section" and existing.section_id:
            section = db.query(Section).filter(Section.id == existing.section_id).first()
            if section:
                section_title = section.title
                topic = db.query(Topic).filter(Topic.id == section.topic_id).first()
                if topic:
                    topic_title = topic.title
                lessons = db.query(Lesson).filter(Lesson.section_id == existing.section_id).all()
                knowledge_description = _build_knowledge_summary(lessons)
        elif existing.type == "topic" and existing.topic_id:
            topic = db.query(Topic).filter(Topic.id == existing.topic_id).first()
            if topic:
                topic_title = topic.title
                section_title = f"{topic.title} (Comprehensive)"
                sections = db.query(Section).filter(Section.topic_id == existing.topic_id).all()
                section_ids = [s.id for s in sections]
                lessons = db.query(Lesson).filter(Lesson.section_id.in_(section_ids)).all() if section_ids else []
                knowledge_description = _build_knowledge_summary(lessons, max_chars_per_lesson=500)

        exercise, validation, template = await _generate_validated_exercise(
            language_name=language_name,
            topic_title=topic_title,
            section_title=section_title,
            knowledge_description=knowledge_description,
        )

        # Update the existing row in-place (keeps the same ID)
        test_cases_data = [tc.model_dump() for tc in exercise.test_cases]
        existing.question = exercise.question
        existing.template = template
        existing.test_cases = json.dumps(test_cases_data, ensure_ascii=False)
        existing.solution = exercise.solution
        existing.declarations = exercise.declarations
        existing.knowledge_tags = exercise.knowledge_tags
        existing.hints = exercise.hints

        db.commit()
        db.refresh(existing)
        return _ex_to_response(existing)
    finally:
        _regenerating.discard(exercise_id)


@router.post("/exercises/{exercise_id}/run")
def run_exercise(exercise_id: int, req: RunExerciseRequest, db: Session = Depends(get_db)):
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Exercise not found")

    if len(req.code) > CODE_MAX_LENGTH:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Code too long ({len(req.code)} chars, max {CODE_MAX_LENGTH})",
        )

    try:
        test_cases = json.loads(exercise.test_cases) if isinstance(exercise.test_cases, str) else exercise.test_cases
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Exercise test cases are malformed",
        )

    # Prepend declarations (enum/type/interface/struct) before user code
    # Avoid duplication: the template (derived from solution) may already include them
    declarations = exercise.declarations or ""
    if declarations.strip() and declarations.strip() not in req.code:
        full_code = f"{declarations}\n\n{req.code}"
    else:
        full_code = req.code

    # Save user code to template so it persists across page reloads
    exercise.template = req.code
    db.commit()

    return run_exercise_code(exercise.language, full_code, test_cases)


@router.get("/sections/{section_id}/exercises")
def get_section_exercises(section_id: int, db: Session = Depends(get_db)):
    exercises = db.query(Exercise).filter(
        Exercise.section_id == section_id,
        Exercise.type == "section",
    ).all()
    return [_ex_to_response(e) for e in exercises]


@router.get("/topics/{topic_id}/exercises")
def get_topic_exercises(topic_id: int, db: Session = Depends(get_db)):
    section_ids = [
        s.id for s in db.query(Section).filter(Section.topic_id == topic_id).all()
    ]
    exercises = db.query(Exercise).filter(
        Exercise.section_id.in_(section_ids) | (Exercise.topic_id == topic_id)
    ).all()
    return [_ex_to_response(e) for e in exercises]
