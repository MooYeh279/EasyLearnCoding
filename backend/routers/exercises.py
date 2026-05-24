import json
from fastapi import APIRouter, Depends, HTTPException
from http import HTTPStatus
from sqlalchemy.orm import Session
from pydantic import BaseModel

from config import CODE_MAX_LENGTH
from database import get_db
from models import Exercise, Section, Topic, Lesson
from services.ai_service import generate_exercise_async
from services.exercise_service import validate_exercise
from logger import get_logger

logger = get_logger("exercises")
router = APIRouter(prefix="/api", tags=["exercises"])


def _validation_error_detail(validation: dict) -> str:
    """Build a concise error description from validation results for AI feedback."""
    error = validation.get("error", "")
    results = validation.get("results", [])
    if results:
        failed = [r for r in results if not r.get("passed")]
        parts = [f"{f['name']}: {f.get('error', 'test failed')}" for f in failed]
        return "; ".join(parts)
    return error or "Solution could not execute (syntax/runtime error)"


def _build_knowledge_summary(lessons, max_chars_per_lesson: int = 500) -> str:
    """Build a knowledge description from lesson content, not just titles."""
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


class ExerciseResponse(BaseModel):
    id: int
    question: str
    template: str
    test_cases: str
    knowledge_tags: list[str] | None
    hints: list[str] | None
    section_id: int | None
    type: str


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

    # 1. AI generates the exercise (retry once on syntax/runtime errors)
    MAX_ATTEMPTS = 2
    exercise_data = None
    validation = None
    for attempt in range(MAX_ATTEMPTS):
        error_feedback = None
        if attempt > 0 and validation:
            error_feedback = _validation_error_detail(validation)
            logger.info("Retrying exercise generation for section %s (attempt %d/%d): %s",
                        section_id, attempt + 1, MAX_ATTEMPTS, error_feedback[:80])
        try:
            exercise_data = await generate_exercise_async(
                topic_title=topic.title,
                language_name=language_name,
                section_title=section.title,
                knowledge_description=knowledge_description,
                error_feedback=error_feedback,
            )
        except Exception as e:
            logger.warning("Section exercise generation failed for section %s: %s", section_id, e)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="AI generation failed",
            )

        # 2. Validate with reference solution
        test_cases = exercise_data.get("test_cases", [])
        solution = exercise_data.get("solution", "")
        validation = validate_exercise(language_name, solution, test_cases)

        if validation.get("all_passed"):
            break

        results = validation.get("results", [])
        failed_cases = [r for r in results if not r.get("passed")]
        all_failed = len(failed_cases) == len(results) if results else False

        # Log failure details so we can diagnose WHY
        error_detail = "; ".join(
            f"{f['name']}: {f.get('error', 'unknown')}" for f in failed_cases
        ) if failed_cases else validation.get("error", "unknown")
        logger.warning(
            "Exercise validation FAILED for section %s: %d/%d tests failed — %s",
            section_id, len(failed_cases), len(results) if results else 1, error_detail,
        )

        # If ALL tests failed, the solution likely has a syntax/runtime error → retry.
        # If only SOME failed, it's a logic error → don't retry.
        if not all_failed:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Generated exercise failed validation",
                    "failed_cases": failed_cases,
                    "validation_error": validation.get("error", ""),
                    "all_passed": validation.get("all_passed"),
                },
            )
        # all_failed → fall through to retry (or raise after loop exhausts)
    else:
        # All retries exhausted without passing
        logger.warning(
            "Exercise validation FAILED after %d retries for section %s: %s",
            MAX_ATTEMPTS, section_id, validation.get("error", "unknown"),
        )
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "message": "Generated exercise failed validation after retries",
                "validation_error": validation.get("error", ""),
                "all_passed": validation.get("all_passed"),
            },
        )

    # 3. Save to database
    question = exercise_data.get("question", "")
    if not question:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="AI generation did not produce a question",
        )

    exercise = Exercise(
        section_id=section_id,
        type="section",
        language=language_name,
        question=question,
        template=exercise_data.get("template", ""),
        test_cases=json.dumps(test_cases, ensure_ascii=False),
        solution=solution,
        knowledge_tags=exercise_data.get("knowledge_tags", []),
        hints=exercise_data.get("hints", []),
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return _ex_to_response(exercise)


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

    # 1. AI generates the exercise (retry once on syntax/runtime errors)
    MAX_ATTEMPTS = 2
    exercise_data = None
    validation = None
    for attempt in range(MAX_ATTEMPTS):
        error_feedback = None
        if attempt > 0 and validation:
            error_feedback = _validation_error_detail(validation)
            logger.info("Retrying topic exercise generation for topic %s (attempt %d/%d): %s",
                        topic_id, attempt + 1, MAX_ATTEMPTS, error_feedback[:80])
        try:
            exercise_data = await generate_exercise_async(
                topic_title=topic.title,
                language_name=language_name,
                section_title=f"{topic.title} (Comprehensive)",
                knowledge_description=knowledge_description,
                error_feedback=error_feedback,
            )
        except Exception as e:
            logger.warning("Topic exercise generation failed for topic %s: %s", topic_id, e)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="AI generation failed",
            )

        test_cases = exercise_data.get("test_cases", [])
        solution = exercise_data.get("solution", "")
        validation = validate_exercise(language_name, solution, test_cases)

        if validation.get("all_passed"):
            break

        results = validation.get("results", [])
        failed_cases = [r for r in results if not r.get("passed")]
        all_failed = len(failed_cases) == len(results) if results else False

        error_detail = "; ".join(
            f"{f['name']}: {f.get('error', 'unknown')}" for f in failed_cases
        ) if failed_cases else validation.get("error", "unknown")
        logger.warning(
            "Topic exercise validation FAILED for topic %s: %d/%d tests failed — %s",
            topic_id, len(failed_cases), len(results) if results else 1, error_detail,
        )

        if not all_failed:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Generated exercise failed validation",
                    "failed_cases": failed_cases,
                    "validation_error": validation.get("error", ""),
                    "all_passed": validation.get("all_passed"),
                },
            )
        # all_failed → fall through to retry
    else:
        logger.warning(
            "Topic exercise validation FAILED after %d retries for topic %s: %s",
            MAX_ATTEMPTS, topic_id, validation.get("error", "") if validation else "unknown",
        )
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "message": "Generated exercise failed validation after retries",
                "validation_error": validation.get("error", "") if validation else "",
                "all_passed": validation.get("all_passed") if validation else False,
            },
        )

    question = exercise_data.get("question", "")
    if not question:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="AI generation did not produce a question",
        )

    exercise = Exercise(
        type="topic",
        topic_id=topic_id,
        language=language_name,
        question=question,
        template=exercise_data.get("template", ""),
        test_cases=json.dumps(test_cases, ensure_ascii=False),
        solution=solution,
        knowledge_tags=exercise_data.get("knowledge_tags", []),
        hints=exercise_data.get("hints", []),
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return _ex_to_response(exercise)


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

    result = validate_exercise(exercise.language, req.code, test_cases)
    return result


@router.get("/sections/{section_id}/exercises")
def get_section_exercises(section_id: int, db: Session = Depends(get_db)):
    exercises = db.query(Exercise).filter(
        Exercise.section_id == section_id,
        Exercise.type == "section",
    ).all()
    return [_ex_to_response(e) for e in exercises]


@router.get("/topics/{topic_id}/exercises")
def get_topic_exercises(topic_id: int, db: Session = Depends(get_db)):
    # Return section exercises for this topic's sections AND topic-level exercises
    section_ids = [
        s.id for s in db.query(Section).filter(Section.topic_id == topic_id).all()
    ]
    exercises = db.query(Exercise).filter(
        Exercise.section_id.in_(section_ids) | (Exercise.topic_id == topic_id)
    ).all()
    return [_ex_to_response(e) for e in exercises]
