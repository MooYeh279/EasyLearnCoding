from models import Language, Course, Topic, TopicStatus


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
