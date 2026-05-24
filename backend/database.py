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


def _column_nullable(table: str, column: str) -> bool:
    import sqlalchemy
    insp = sqlalchemy.inspect(engine)
    for c in insp.get_columns(table):
        if c["name"] == column:
            return c["nullable"]
    return False


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
    if not _column_exists("exercises", "language"):
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE exercises ADD COLUMN language TEXT NOT NULL DEFAULT 'python'"
            ))
            conn.commit()
    if not _column_exists("exercises", "topic_id"):
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE exercises ADD COLUMN topic_id INTEGER REFERENCES topics(id)"
            ))
            conn.commit()
    if not _column_nullable("exercises", "lesson_id"):
        with engine.connect() as conn:
            sql = __import__("sqlalchemy").text
            # SQLite does not support ALTER COLUMN to drop NOT NULL,
            # so rebuild the exercises table with the correct schema.
            conn.execute(sql(
                "CREATE TABLE exercises_new ("
                "id INTEGER PRIMARY KEY,"
                "lesson_id INTEGER REFERENCES lessons(id),"
                "section_id INTEGER REFERENCES sections(id),"
                "topic_id INTEGER REFERENCES topics(id),"
                "type TEXT NOT NULL DEFAULT 'section',"
                "question TEXT NOT NULL,"
                "template TEXT DEFAULT '',"
                "test_cases TEXT DEFAULT '',"
                "solution TEXT DEFAULT '',"
                "language TEXT NOT NULL DEFAULT 'python',"
                "knowledge_tags JSON DEFAULT '[]',"
                "hints JSON DEFAULT '[]'"
                ")"
            ))
            conn.execute(sql(
                "INSERT INTO exercises_new (id, lesson_id, section_id, topic_id, type, question, template, test_cases, solution, language, knowledge_tags, hints)"
                "SELECT id, lesson_id, section_id, topic_id, type, question, template, test_cases, solution, language, knowledge_tags, hints FROM exercises"
            ))
            conn.execute(sql("DROP TABLE exercises"))
            conn.execute(sql("ALTER TABLE exercises_new RENAME TO exercises"))
            conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
