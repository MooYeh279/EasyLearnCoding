import json
import re

import pytest
from models import Language, Course, Topic, TopicStatus
from routers.topics import _repair_json


def _extract_json(text: str) -> str:
    m = re.search(r"```(?:json)?[^\n]*\n(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return text


class TestRepairJson:
    def test_valid_json_unchanged(self):
        text = '{"title": "hello world", "desc": "no quotes here"}'
        repaired = _repair_json(text)
        assert json.loads(repaired) == json.loads(text)

    def test_unescaped_chinese_quote_fixed(self):
        text = '{"title": "让函数拥有"记忆""}'
        repaired = _repair_json(text)
        data = json.loads(repaired)
        assert data["title"] == '让函数拥有"记忆"'

    def test_multiple_unescaped_quotes(self):
        text = '{"a": "能"记住"外部"变量"}'
        repaired = _repair_json(text)
        data = json.loads(repaired)
        assert data["a"] == '能"记住"外部"变量'

    def test_already_escaped_quotes_unchanged(self):
        text = '{"title": "hello \\"world\\""}'
        repaired = _repair_json(text)
        data = json.loads(repaired)
        assert data["title"] == 'hello "world"'

    def test_quote_before_comma_not_escaped(self):
        text = '{"a": "hello", "b": "world"}'
        repaired = _repair_json(text)
        data = json.loads(repaired)
        assert data == {"a": "hello", "b": "world"}

    def test_with_markdown_fences(self):
        text = '''```json
{"sections": [{"title": "初识闭包 — 让函数拥有"记忆"", "description": "了解"闭包"概念"}]}
```'''
        cleaned = _extract_json(text)
        repaired = _repair_json(cleaned)
        data = json.loads(repaired)
        assert data["sections"][0]["title"] == '初识闭包 — 让函数拥有"记忆"'
        assert data["sections"][0]["description"] == '了解"闭包"概念'

    def test_real_world_error_case(self):
        text = '''现在我对闭包的教学内容有了清晰把握，可以开始生成大纲了。

闭包是一个**中等偏窄**的主题——核心概念集中，但应用场景丰富。

```json
{
  "sections": [
    {
      "title": "第一章：初识闭包 — 让函数拥有"记忆"",
      "description": "理解"闭包"的基本概念"
    }
  ]
}
```'''
        cleaned = _extract_json(text)
        repaired = _repair_json(cleaned)
        data = json.loads(repaired)
        assert len(data["sections"]) == 1
        assert data["sections"][0]["title"] == '第一章：初识闭包 — 让函数拥有"记忆"'

    def test_empty_string(self):
        assert _repair_json("") == ""

    def test_no_quotes(self):
        text = "12345"
        assert _repair_json(text) == text


def test_create_topic(client, db):
    lang = Language(id=30, name="rust", display_name="Rust")
    db.add(lang)
    db.commit()
    course = Course(language_id=lang.id, title="Rust 学习")
    db.add(course)
    db.commit()
    resp = client.post(f"/api/courses/{course.id}/topics", json={"title": "Ownership"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Ownership"
    assert data["status"] == "draft"


def test_get_topic(client, db):
    lang = Language(id=31, name="go", display_name="Go")
    db.add(lang)
    db.commit()
    course = Course(language_id=lang.id, title="Go 学习")
    db.add(course)
    db.commit()
    topic = Topic(course_id=course.id, title="Goroutines", status=TopicStatus.draft)
    db.add(topic)
    db.commit()
    resp = client.get(f"/api/topics/{topic.id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Goroutines"


class TestBriefMode:
    """GET /topics/{id}?brief=true returns lightweight response."""

    def test_brief_returns_essential_fields(self, client, db):
        from models import Section, Lesson
        lang = Language(id=50, name="brief_test", display_name="Brief Test")
        db.add(lang); db.commit()
        course = Course(language_id=lang.id, title="Brief Course")
        db.add(course); db.commit()
        topic = Topic(course_id=course.id, title="Brief Topic",
                      status=TopicStatus.generating_content,
                      generation_progress={"current": 2, "total": 5, "current_section": "Ch1", "current_lesson": "L2"})
        db.add(topic); db.commit()
        sec = Section(topic_id=topic.id, title="Ch1", order=0)
        db.add(sec); db.commit()
        les = Lesson(section_id=sec.id, title="L1", order=0, content="")
        db.add(les); db.commit()
        les2 = Lesson(section_id=sec.id, title="L2", order=1, content='[{"id":"a","type":"markdown","content":"hello"}]')
        db.add(les2); db.commit()

        resp = client.get(f"/api/topics/{topic.id}?brief=true")
        assert resp.status_code == 200
        data = resp.json()
        # Essential fields present
        assert data["status"] == "generating_content"
        assert data["generation_progress"]["current"] == 2
        assert data["generation_progress"]["total"] == 5
        # Sections with lessons
        assert len(data["sections"]) == 1
        assert len(data["sections"][0]["lessons"]) == 2
        # Lessons have has_content but NOT raw content
        l1 = data["sections"][0]["lessons"][0]
        l2 = data["sections"][0]["lessons"][1]
        assert l1["has_content"] is False
        assert l2["has_content"] is True
        assert "content" not in l1
        assert "content" not in l2

    def test_brief_no_sections(self, client, db):
        lang = Language(id=51, name="brief_empty", display_name="Brief Empty")
        db.add(lang); db.commit()
        course = Course(language_id=lang.id, title="Brief Empty Course")
        db.add(course); db.commit()
        topic = Topic(course_id=course.id, title="No Sections", status=TopicStatus.draft)
        db.add(topic); db.commit()

        resp = client.get(f"/api/topics/{topic.id}?brief=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "draft"
        assert data["sections"] == []

    def test_full_mode_unchanged(self, client, db):
        """Non-brief mode still returns full SQLAlchemy model."""
        from models import Section, Lesson
        lang = Language(id=52, name="full_test", display_name="Full Test")
        db.add(lang); db.commit()
        course = Course(language_id=lang.id, title="Full Course")
        db.add(course); db.commit()
        topic = Topic(course_id=course.id, title="Full Topic", status=TopicStatus.draft)
        db.add(topic); db.commit()
        sec = Section(topic_id=topic.id, title="S1", order=0)
        db.add(sec); db.commit()
        les = Lesson(section_id=sec.id, title="L1", order=0, content="some content", lesson_type="concept")
        db.add(les); db.commit()

        resp = client.get(f"/api/topics/{topic.id}")
        assert resp.status_code == 200
        data = resp.json()
        # Full response has lesson_type and content
        assert data["sections"][0]["lessons"][0]["lesson_type"] == "concept"
        assert data["sections"][0]["lessons"][0]["content"] == "some content"


class TestMarkContentReady:
    def test_sets_status_and_clears_progress(self, db):
        from routers.topics import _mark_content_ready
        from models import Section, Lesson
        lang = Language(id=60, name="mark_ready", display_name="Mark Ready")
        db.add(lang); db.commit()
        course = Course(language_id=lang.id, title="Course")
        db.add(course); db.commit()
        topic = Topic(course_id=course.id, title="Topic",
                      status=TopicStatus.generating_content,
                      generation_progress={"current": 3, "total": 5})
        db.add(topic); db.commit()

        _mark_content_ready(topic.id)

        # Need fresh query since _mark_content_ready uses its own session
        from database import SessionLocal
        s = SessionLocal()
        try:
            t = s.query(Topic).filter(Topic.id == topic.id).first()
            assert t.status == TopicStatus.content_ready
            assert t.generation_progress is None
        finally:
            s.close()


class TestUpdateProgress:
    def test_updates_progress_in_db(self, db):
        from routers.topics import _update_progress
        lang = Language(id=61, name="upd_prog", display_name="Update Progress")
        db.add(lang); db.commit()
        course = Course(language_id=lang.id, title="Course")
        db.add(course); db.commit()
        topic = Topic(course_id=course.id, title="Topic",
                      status=TopicStatus.generating_content,
                      generation_progress={"current": 0, "total": 5, "current_section": "", "current_lesson": ""})
        db.add(topic); db.commit()

        _update_progress(topic.id, 2, 5, {"section_title": "Ch1", "lesson_title": "L2"})

        from database import SessionLocal
        s = SessionLocal()
        try:
            t = s.query(Topic).filter(Topic.id == topic.id).first()
            assert t.generation_progress["current"] == 2
            assert t.generation_progress["total"] == 5
            assert t.generation_progress["current_section"] == "Ch1"
            assert t.generation_progress["current_lesson"] == "L2"
        finally:
            s.close()


def test_delete_topic(client, db):
    lang = Language(id=32, name="ruby", display_name="Ruby")
    db.add(lang)
    db.commit()
    course = Course(language_id=lang.id, title="Ruby 学习")
    db.add(course)
    db.commit()
    topic = Topic(course_id=course.id, title="Blocks", status=TopicStatus.draft)
    db.add(topic)
    db.commit()
    tid = topic.id
    resp = client.delete(f"/api/topics/{tid}")
    assert resp.status_code == 204
    assert db.query(Topic).filter(Topic.id == tid).first() is None
