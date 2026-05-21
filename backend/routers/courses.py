from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from database import get_db
from models import Course

router = APIRouter(prefix="/api/courses", tags=["courses"])

@router.get("")
def list_courses(language_id: int = None, db: Session = Depends(get_db)):
    query = db.query(Course).options(selectinload(Course.topics), selectinload(Course.language))
    if language_id is not None:
        query = query.filter(Course.language_id == language_id)
    return query.all()

@router.get("/{course_id}")
def get_course(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).options(selectinload(Course.topics), selectinload(Course.language)).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")
    return course
