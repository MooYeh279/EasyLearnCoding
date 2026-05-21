from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _column_exists(table: str, column: str) -> bool:
    import sqlalchemy
    insp = sqlalchemy.inspect(engine)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def migrate():
    if not _column_exists("topics", "generation_progress"):
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE topics ADD COLUMN generation_progress JSON"
            ))
            conn.commit()
    if not _column_exists("languages", "env_config"):
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE languages ADD COLUMN env_config JSON"
            ))
            conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
