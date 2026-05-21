from database import SessionLocal, engine, Base
from models import Language, Course

Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()
    try:
        languages = [
            Language(id=1, name="python", display_name="Python"),
            Language(id=2, name="javascript", display_name="JavaScript"),
            Language(id=3, name="typescript", display_name="TypeScript"),
            Language(id=4, name="c",   display_name="C"),
            Language(id=5, name="cpp", display_name="C++"),
        ]
        for lang in languages:
            existing = db.query(Language).filter(Language.id == lang.id).first()
            if not existing:
                db.add(lang)
        db.commit()

        for lang in db.query(Language).all():
            course_exists = (
                db.query(Course).filter(Course.language_id == lang.id).first()
            )
            if not course_exists:
                db.add(
                    Course(
                        id=lang.id,
                        language_id=lang.id,
                        title=f"{lang.display_name} 学习",
                    )
                )
        db.commit()

        print("Seed data inserted.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
