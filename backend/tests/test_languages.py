from models import Language

def test_list_languages(client, db):
    db.add(Language(id=10, name="testlang", display_name="TestLang"))
    db.commit()
    resp = client.get("/api/languages")
    assert resp.status_code == 200
    langs = resp.json()
    names = [l["name"] for l in langs]
    assert "testlang" in names

def test_get_language_not_found(client):
    resp = client.get("/api/languages/9999")
    assert resp.status_code == 404
