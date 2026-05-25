"""Tests for exercise regeneration endpoint."""
import json
from unittest.mock import patch, AsyncMock

from services.exercise_schema import (
    FunctionSignature, TestCaseSpec, RawExerciseOutput, ValidationResult,
)
from services.exercise_service import validate_exercise


def _make_raw_exercise() -> RawExerciseOutput:
    return RawExerciseOutput(
        question="Implement the add function",
        solution="def add(a, b):\n    return a + b",
        function_signatures=[FunctionSignature(name="add", params="a, b", return_type="")],
        test_cases=[
            TestCaseSpec(name="1+2", input="add(1, 2)", expected="3"),
        ],
        hints=["Think about addition"],
    )


def test_regenerate_section_exercise(client, db):
    """Regenerate should update the exercise in-place, keeping the same ID."""
    from models import Course, Language, Topic, Section, Lesson, Exercise

    # Setup: language, course, topic, section, lesson, exercise
    lang = Language(name="python", display_name="Python")
    db.add(lang)
    db.commit()

    course = Course(title="Test Course", language_id=lang.id)
    db.add(course)
    db.commit()

    topic = Topic(title="Test Topic", course_id=course.id)
    db.add(topic)
    db.commit()

    section = Section(title="Test Section", topic_id=topic.id, order=1)
    db.add(section)
    db.commit()

    lesson = Lesson(title="Lesson 1", section_id=section.id, content="x + y adds numbers", order=1)
    db.add(lesson)
    db.commit()

    # Create original exercise
    original = Exercise(
        section_id=section.id,
        type="section",
        language="python",
        question="Original question",
        template="def add(a, b):\n    pass",
        test_cases=json.dumps([{"name": "t1", "input": "add(1,1)", "expected": "2", "is_string": False}]),
        solution="def add(a, b):\n    return a + b",
        declarations="",
        hints=["old hint"],
    )
    db.add(original)
    db.commit()
    original_id = original.id

    # Mock AI generation to return a new exercise
    new_exercise = _make_raw_exercise()
    with patch("routers.exercises.generate_exercise_async", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = new_exercise
        response = client.post(f"/api/exercises/{original_id}/regenerate")

    assert response.status_code == 200
    data = response.json()
    # Same ID — exercise updated in-place
    assert data["id"] == original_id
    # Content was updated
    assert data["question"] == "Implement the add function"
    assert data["hints"] == ["Think about addition"]


def test_regenerate_topic_exercise(client, db):
    """Regenerate a topic-level (comprehensive) exercise."""
    from models import Course, Language, Topic, Section, Exercise

    lang = Language(name="python", display_name="Python")
    db.add(lang)
    db.commit()

    course = Course(title="Test Course", language_id=lang.id)
    db.add(course)
    db.commit()

    topic = Topic(title="Test Topic", course_id=course.id)
    db.add(topic)
    db.commit()

    # Create original topic-level exercise
    original = Exercise(
        topic_id=topic.id,
        type="topic",
        language="python",
        question="Original comprehensive question",
        template="def add(a, b):\n    pass",
        test_cases=json.dumps([{"name": "t1", "input": "add(1,1)", "expected": "2", "is_string": False}]),
        solution="def add(a, b):\n    return a + b",
        declarations="",
        hints=["old hint"],
    )
    db.add(original)
    db.commit()
    original_id = original.id

    new_exercise = _make_raw_exercise()
    with patch("routers.exercises.generate_exercise_async", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = new_exercise
        response = client.post(f"/api/exercises/{original_id}/regenerate")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == original_id
    assert data["question"] == "Implement the add function"


def test_regenerate_not_found(client):
    """Regenerate a non-existent exercise returns 404."""
    response = client.post("/api/exercises/99999/regenerate")
    assert response.status_code == 404


def test_regenerate_preserves_id(client, db):
    """Multiple regenerations keep the same exercise ID."""
    from models import Course, Language, Topic, Section, Lesson, Exercise

    lang = Language(name="python", display_name="Python")
    db.add(lang)
    db.commit()

    course = Course(title="Test Course", language_id=lang.id)
    db.add(course)
    db.commit()

    topic = Topic(title="Test Topic", course_id=course.id)
    db.add(topic)
    db.commit()

    section = Section(title="Test Section", topic_id=topic.id, order=1)
    db.add(section)
    db.commit()

    lesson = Lesson(title="Lesson 1", section_id=section.id, content="x + y adds numbers", order=1)
    db.add(lesson)
    db.commit()

    original = Exercise(
        section_id=section.id,
        type="section",
        language="python",
        question="Q1",
        template="pass",
        test_cases="[]",
        solution="def f(): pass",
        declarations="",
        hints=[],
    )
    db.add(original)
    db.commit()
    original_id = original.id

    new_exercise = _make_raw_exercise()
    with patch("routers.exercises.generate_exercise_async", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = new_exercise
        r1 = client.post(f"/api/exercises/{original_id}/regenerate")
        r2 = client.post(f"/api/exercises/{original_id}/regenerate")

    assert r1.json()["id"] == original_id
    assert r2.json()["id"] == original_id
