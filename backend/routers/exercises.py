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
    knowledge_description = ", ".join(l.title for l in lessons)

    # 1. AI generates the exercise
    try:
        exercise_data = await generate_exercise_async(
            topic_title=topic.title,
            language_name=language_name,
            section_title=section.title,
            knowledge_description=knowledge_description,
        )
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"AI generation failed: {str(e)}",
        )

    # 2. Validate with reference solution
    test_cases = exercise_data.get("test_cases", [])
    solution = exercise_data.get("solution", "")
    validation = validate_exercise(language_name, solution, test_cases)

    if not validation.get("all_passed"):
        failed_cases = [r for r in validation.get("results", []) if not r.get("passed")]
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "message": "Generated exercise failed validation",
                "failed_cases": failed_cases,
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
    knowledge_description = ", ".join(s.title for s in sections)

    try:
        exercise_data = await generate_exercise_async(
            topic_title=topic.title,
            language_name=language_name,
            section_title=f"{topic.title} (Comprehensive)",
            knowledge_description=knowledge_description,
        )
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"AI generation failed: {str(e)}",
        )

    test_cases = exercise_data.get("test_cases", [])
    solution = exercise_data.get("solution", "")
    validation = validate_exercise(language_name, solution, test_cases)

    if not validation.get("all_passed"):
        failed_cases = [r for r in validation.get("results", []) if not r.get("passed")]
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "message": "Generated exercise failed validation",
                "failed_cases": failed_cases,
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
        Exercise.section_id.in_(section_ids) | (Exercise.type == "topic")
    ).all()
    return [_ex_to_response(e) for e in exercises]
