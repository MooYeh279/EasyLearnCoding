"""Tests for lesson CRUD endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from models import Language, Course, Topic, Section, Lesson


def create_lesson(db: Session) -> int:
    """Create a full chain: language -> course -> topic -> section -> lesson."""
    lang = Language(name="python", display_name="Python")
    db.add(lang)
    db.flush()
    course = Course(language_id=lang.id, title="Test Course")
    db.add(course)
    db.flush()
    topic = Topic(course_id=course.id, title="Test Topic", status="content_ready")
    db.add(topic)
    db.flush()
    section = Section(topic_id=topic.id, title="Test Section", order=0)
    db.add(section)
    db.flush()
    lesson = Lesson(section_id=section.id, title="Test Lesson", order=0,
                    content='[{"id":"c1","type":"markdown","content":"Hello"}]',
                    lesson_type="concept")
    db.add(lesson)
    db.commit()
    return lesson.id


class TestGetLesson:
    def test_get_existing_lesson(self, client, db):
        lesson_id = create_lesson(db)
        r = client.get(f"/api/lessons/{lesson_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Test Lesson"
        assert "content" in data

    def test_get_nonexistent_lesson(self, client):
        r = client.get("/api/lessons/99999")
        assert r.status_code == 404


class TestUpdateLesson:
    def test_update_lesson_content(self, client, db):
        lesson_id = create_lesson(db)
        new_content = '[{"id":"c2","type":"markdown","content":"Updated"}]'
        r = client.put(f"/api/lessons/{lesson_id}", json={"content": new_content})
        assert r.status_code == 200
        data = r.json()
        assert data["content"] == new_content
