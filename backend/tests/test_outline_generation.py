import json
import time
from unittest.mock import patch, AsyncMock
from models import Language, Course, Topic, TopicStatus

MOCK_OUTLINE = {
    "sections": [
        {
            "title": "Basics",
            "description": "Learn the basics",
            "lessons": [{"title": "Intro"}, {"title": "Setup"}],
        }
    ]
}

MOCK_LESSON = "## Intro\n\nThis is lesson content."


async def _mock_generate_lesson_async(**kwargs):
    return MOCK_LESSON


@patch("routers.topics.generate_outline_async", new_callable=AsyncMock)
def test_generate_outline_endpoint(mock_gen, client, db):
    mock_gen.return_value = MOCK_OUTLINE
    lang = Language(id=40, name="java", display_name="Java")
    db.add(lang)
    db.commit()
    course = Course(language_id=lang.id, title="Java 学习")
    db.add(course)
    db.commit()
    topic = Topic(course_id=course.id, title="Streams", status=TopicStatus.draft)
    db.add(topic)
    db.commit()

    resp = client.post(f"/api/topics/{topic.id}/generate-outline", json={"topic_title": "Streams"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sections"][0]["title"] == "Basics"

    db.refresh(topic)
    assert topic.status == TopicStatus.outline_ready


@patch("services.ai_service.generate_lesson_async", side_effect=_mock_generate_lesson_async)
@patch("routers.topics.generate_outline_async", new_callable=AsyncMock)
def test_generate_content_endpoint(mock_outline, mock_lesson_async, client, db):
    lang = Language(id=41, name="kotlin", display_name="Kotlin")
    db.add(lang)
    db.commit()
    course = Course(language_id=lang.id, title="Kotlin 学习")
    db.add(course)
    db.commit()
    topic = Topic(course_id=course.id, title="Coroutines", status=TopicStatus.outline_ready)
    db.add(topic)
    db.commit()

    from models import TopicOutline
    db.add(TopicOutline(topic_id=topic.id, sections_json=MOCK_OUTLINE))
    db.commit()

    resp = client.post(f"/api/topics/{topic.id}/generate-content")
    assert resp.status_code == 200
    assert resp.json()["status"] == "content_ready"

    resp2 = client.get(f"/api/topics/{topic.id}")
    assert resp2.status_code == 200
    topic_data = resp2.json()
    assert len(topic_data["sections"]) == 1
    assert len(topic_data["sections"][0]["lessons"]) == 2


@patch("routers.topics.generate_outline_async", new_callable=AsyncMock)
def test_generate_outline_with_feedback(mock_gen, client, db):
    mock_gen.return_value = {
        "sections": [{"title": "Revised", "description": "d", "lessons": [{"title": "X"}]}]
    }
    lang = Language(id=42, name="swift", display_name="Swift")
    db.add(lang)
    db.commit()
    course = Course(language_id=lang.id, title="Swift 学习")
    db.add(course)
    db.commit()
    topic = Topic(course_id=course.id, title="Combine", status=TopicStatus.outline_ready)
    db.add(topic)
    db.commit()

    from models import TopicOutline
    db.add(TopicOutline(topic_id=topic.id, sections_json={"sections": [{"title": "Old"}]}))
    db.commit()

    resp = client.post(f"/api/topics/{topic.id}/generate-outline",
                       json={"topic_title": "Combine", "feedback": "Make it shorter"})
    assert resp.status_code == 200
    assert resp.json()["sections"][0]["title"] == "Revised"


@patch("routers.topics.generate_outline_async", new_callable=AsyncMock)
def test_generate_outline_with_content_language(mock_gen, client, db):
    mock_gen.return_value = MOCK_OUTLINE
    lang = Language(id=43, name="go", display_name="Go")
    db.add(lang)
    db.commit()
    course = Course(language_id=lang.id, title="Go 学习")
    db.add(course)
    db.commit()
    topic = Topic(course_id=course.id, title="Goroutines", status=TopicStatus.draft)
    db.add(topic)
    db.commit()

    resp = client.post(f"/api/topics/{topic.id}/generate-outline",
                       json={"topic_title": "Goroutines", "content_language": "en"})
    assert resp.status_code == 200
    mock_gen.assert_called_once()
    assert mock_gen.call_args[1]["content_language"] == "en"


@patch("services.ai_service.generate_lesson_async", side_effect=_mock_generate_lesson_async)
def test_generate_content_stream(mock_lesson_async, client, db):
    from tests.conftest import TestingSessionLocal
    import routers.topics as topics_module

    lang = Language(id=44, name="ruby", display_name="Ruby")
    db.add(lang)
    db.commit()
    course = Course(language_id=lang.id, title="Ruby 学习")
    db.add(course)
    db.commit()
    topic = Topic(course_id=course.id, title="Blocks", status=TopicStatus.outline_ready)
    db.add(topic)
    db.commit()

    from models import TopicOutline
    db.add(TopicOutline(topic_id=topic.id, sections_json=MOCK_OUTLINE))
    db.commit()

    with patch.object(topics_module, "SessionLocal", side_effect=TestingSessionLocal):
        resp = client.post(f"/api/topics/{topic.id}/generate-content-stream",
                           json={"content_language": "zh"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "generation_started"

    # Wait for background thread (mock returns instantly)
    time.sleep(0.5)

    resp2 = client.get(f"/api/topics/{topic.id}")
    assert resp2.status_code == 200
    topic_data = resp2.json()
    assert len(topic_data["sections"]) == 1
    assert len(topic_data["sections"][0]["lessons"]) == 2
    assert topic_data["status"] == "content_ready"
    assert topic_data["generation_progress"] is None


@patch("services.ai_service.generate_lesson_async")
def test_generate_content_stream_error_event(mock_lesson_async, client, db):
    from tests.conftest import TestingSessionLocal
    import routers.topics as topics_module

    async def _mock_error(**kwargs):
        raise Exception("AI timeout")

    async def _mock_ok(**kwargs):
        return "## OK"

    call_count = [0]

    async def _mock_alternating(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return await _mock_ok(**kwargs)
        else:
            return await _mock_error(**kwargs)

    mock_lesson_async.side_effect = _mock_alternating

    lang = Language(id=45, name="rust", display_name="Rust")
    db.add(lang)
    db.commit()
    course = Course(language_id=lang.id, title="Rust 学习")
    db.add(course)
    db.commit()
    topic = Topic(course_id=course.id, title="Ownership", status=TopicStatus.outline_ready)
    db.add(topic)
    db.commit()

    from models import TopicOutline
    db.add(TopicOutline(topic_id=topic.id, sections_json=MOCK_OUTLINE))
    db.commit()

    with patch.object(topics_module, "SessionLocal", side_effect=TestingSessionLocal):
        resp = client.post(f"/api/topics/{topic.id}/generate-content-stream",
                           json={"content_language": "zh"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "generation_started"

    # Wait for background thread
    time.sleep(0.5)

    resp2 = client.get(f"/api/topics/{topic.id}")
    topic_data = resp2.json()
    assert len(topic_data["sections"][0]["lessons"]) == 2
    # Failed lesson content should not contain error messages
    failed_lesson = topic_data["sections"][0]["lessons"][1]
    assert "Generation failed" not in (failed_lesson["content"] or "")
    # The generation_progress should be cleared for content_ready status
    # (failed_lesson_ids tracking is ephemeral during generation)


class TestMarkdownToCells:
    """Unit tests for _markdown_to_cells conversion function."""

    def test_empty_markdown(self):
        """Empty markdown produces an empty cell list."""
        from services.outline_service import _markdown_to_cells
        result = _markdown_to_cells("")
        cells = json.loads(result)
        assert isinstance(cells, list)
        assert len(cells) == 0

    def test_markdown_with_code_block(self):
        """Markdown with code fences produces both markdown and code cells."""
        from services.outline_service import _markdown_to_cells
        md = "## Section\n\nSome text here.\n\n```python\nprint('hello')\n```\n\nMore text."
        result = _markdown_to_cells(md)
        cells = json.loads(result)
        types = [c["type"] for c in cells]
        assert "code" in types
        assert "markdown" in types


class TestGenerateContentEdgeCases:
    """Edge case tests for generate_content_concurrent."""

    def test_generate_content_preserves_existing(self, client, db):
        """Existing lesson content should NOT be regenerated on second run."""
        from models import Language, Course, Topic, TopicStatus
        from models import Lesson as LessonModel
        from unittest.mock import patch, AsyncMock

        lang = Language(name="python", display_name="Python")
        db.add(lang)
        db.commit()

        course = Course(language_id=lang.id, title="TC")
        db.add(course)
        db.commit()

        topic = Topic(course_id=course.id, title="T", status=TopicStatus.outline_ready)
        db.add(topic)
        db.commit()
        topic_id = topic.id

        # Generate outline
        with patch("routers.topics.generate_outline_async", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "sections": [{"title": "S1", "description": "desc", "lessons": [{"title": "L1"}]}]
            }
            client.post(f"/api/topics/{topic_id}/generate-outline", json={"topic_title": "T"})

        # Generate content first time
        with patch("services.ai_service.generate_lesson_async", new_callable=AsyncMock) as mock_lesson:
            mock_lesson.return_value = "# Content"
            client.post(f"/api/topics/{topic_id}/generate-content", json={})

        # Re-query topic with fresh session to see committed data
        db.expire_all()
        topic = db.query(Topic).filter(Topic.id == topic_id).first()

        # Verify content was generated
        original_contents = {}
        for sec in topic.sections:
            for les in (sec.lessons or []):
                if les.content and len(les.content) > 10 and not les.content.startswith("[Generation failed"):
                    original_contents[les.id] = les.content

        assert len(original_contents) > 0, "Should have at least one lesson with content"

        # Reset status to allow regeneration via endpoint
        db.query(Topic).filter(Topic.id == topic_id).update({"status": TopicStatus.outline_ready})
        db.commit()

        # Generate again -- existing content should be preserved
        with patch("services.ai_service.generate_lesson_async", new_callable=AsyncMock) as mock_lesson2:
            mock_lesson2.return_value = "SHOULD NOT REPLACE"
            client.post(f"/api/topics/{topic_id}/generate-content", json={})

        # Re-query and verify content is intact
        db.expire_all()
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        for sec in topic.sections:
            for les in (sec.lessons or []):
                if les.id in original_contents:
                    assert les.content == original_contents[les.id], \
                        "Existing lesson content should be preserved"
