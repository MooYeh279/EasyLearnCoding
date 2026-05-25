import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from main import app

TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

import sqlalchemy
insp = sqlalchemy.inspect(engine)
if "generation_progress" not in [c["name"] for c in insp.get_columns("topics")]:
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("ALTER TABLE topics ADD COLUMN generation_progress JSON"))
        conn.commit()

if "env_config" not in [c["name"] for c in insp.get_columns("languages")]:
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("ALTER TABLE languages ADD COLUMN env_config JSON"))
        conn.commit()

if "topic_id" not in [c["name"] for c in insp.get_columns("exercises")]:
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("ALTER TABLE exercises ADD COLUMN topic_id INTEGER REFERENCES topics(id)"))
        conn.commit()

if "declarations" not in [c["name"] for c in insp.get_columns("exercises")]:
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("ALTER TABLE exercises ADD COLUMN declarations TEXT DEFAULT ''"))
        conn.commit()

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


def _clean_tables(db):
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()


@pytest.fixture(autouse=True)
def clean_db():
    db = TestingSessionLocal()
    _clean_tables(db)
    db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
