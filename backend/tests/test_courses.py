from models import Language, Course

def test_list_courses(client, db):
    lang = Language(id=20, name="clang", display_name="C")
    db.add(lang)
    db.commit()
    db.add(Course(language_id=lang.id, title="C 学习"))
    db.commit()
    resp = client.get(f"/api/courses?language_id={lang.id}")
    assert resp.status_code == 200
    courses = resp.json()
    assert len(courses) == 1
    assert courses[0]["title"] == "C 学习"
