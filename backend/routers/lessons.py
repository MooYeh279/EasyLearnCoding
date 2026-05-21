from fastapi import APIRouter, Depends, HTTPException
from http import HTTPStatus
from sqlalchemy.orm import Session, selectinload
from database import get_db
from models import Lesson

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("/{lesson_id}")
def get_lesson(lesson_id: int, db: Session = Depends(get_db)):
    lesson = db.query(Lesson).options(
        selectinload(Lesson.code_blocks),
        selectinload(Lesson.exercises),
    ).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Lesson not found")
    return lesson
