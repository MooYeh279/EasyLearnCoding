from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Language

router = APIRouter(prefix="/api/languages", tags=["languages"])

@router.get("")
def list_languages(db: Session = Depends(get_db)):
    return db.query(Language).all()

@router.get("/{language_id}")
def get_language(language_id: int, db: Session = Depends(get_db)):
    lang = db.query(Language).filter(Language.id == language_id).first()
    if not lang:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")
    return lang
