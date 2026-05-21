from fastapi import APIRouter, Depends, HTTPException
from http import HTTPStatus
from sqlalchemy.orm import Session, selectinload
from database import get_db
from models import Section

router = APIRouter(prefix="/api/sections", tags=["sections"])


@router.get("/{section_id}")
def get_section(section_id: int, db: Session = Depends(get_db)):
    section = db.query(Section).options(
        selectinload(Section.lessons)
    ).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Section not found")
    return section
