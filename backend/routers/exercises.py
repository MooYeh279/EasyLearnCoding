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
from services.exercise_service import validate_exercise_v2, run_exercise_code
from services.template_generator import generate_template

logger = get_logger("exercises")
router = APIRouter(prefix="/api", tags=["exercises"])

MAX_GENERATION_ATTEMPTS = 3
MAX_STRUCTURE_RETRIES = 2


def _build_knowledge_summary(lessons, max_chars_per_lesson: int = 500) -> str:
    """Build a knowledge description from lesson content."""
    parts = []
    for l in lessons:
        content = (l.content or "").strip()
        if content:
            preview = content[:max_chars_per_lesson]
            if len(content) > max_chars_per_lesson:
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

        validation = validate_exercise_v2(language_name, exercise)

        if validation.valid:
            template = generate_template(language_name, exercise.function_signatures)
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
    knowledge_description = _build_knowledge_summary(lessons, max_chars_per_lesson=300)

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
        knowledge_tags=exercise.knowledge_tags,
        hints=exercise.hints,
    )
    db.add(db_exercise)
    db.commit()
    db.refresh(db_exercise)
    return _ex_to_response(db_exercise)


@router.get("/exercises/{exercise_id}")
def get_exercise(exercise_id: int, db: Session = Depends(get_db)):
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Exercise not found")
    return _ex_to_response(exercise)


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

    return run_exercise_code(exercise.language, req.code, test_cases)


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
