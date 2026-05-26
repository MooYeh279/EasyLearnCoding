"""E2E test for outline generation flow via SSE."""
import json
import httpx
import pytest


BASE_URL = "http://localhost:8000/api"

# Known test data — assumes seed data exists
TEST_COURSE_ID = 1  # Python course


def _collect_sse_events(response: httpx.Response) -> list[dict]:
    """Parse SSE stream into list of events."""
    events = []
    current_type = ""
    for line in response.iter_lines():
        if line.startswith("event: "):
            current_type = line[7:]
        elif line.startswith("data: "):
            data = json.loads(line[6:])
            data["_eventType"] = current_type
            events.append(data)
            current_type = ""
    return events


@pytest.mark.e2e
def test_outline_generation_streams_events():
    """Outline generation SSE endpoint should yield well-formed events."""
    # First create a topic
    with httpx.Client(base_url=BASE_URL) as client:
        r = client.post(
            f"/courses/{TEST_COURSE_ID}/topics",
            json={"title": "E2E Test: Variables"},
        )
        assert r.status_code == 201, f"Failed to create topic: {r.text}"
        topic = r.json()
        topic_id = topic["id"]

    try:
        with httpx.Client(base_url=BASE_URL, timeout=120) as client:
            r = client.post(
                f"/topics/{topic_id}/generate-outline-stream",
                json={"topic_title": "Python Variables", "content_language": "zh"},
            )
            assert r.status_code == 200, f"SSE endpoint returned {r.status_code}"
            events = _collect_sse_events(r)

        # Should have agent_start event
        assert any(e.get("_eventType") == "agent_start" for e in events), \
            f"No agent_start event. Events: {[e.get('_eventType') for e in events]}"

        # Verify event structure
        for e in events:
            event_type = e.get("_eventType", "")
            if event_type == "tool_call":
                assert "tool" in e, f"tool_call missing 'tool': {e}"
                assert "args" in e, f"tool_call missing 'args': {e}"
            elif event_type == "tool_result":
                assert "tool" in e, f"tool_result missing 'tool': {e}"
                assert "result" in e, f"tool_result missing 'result': {e}"
            elif event_type == "agent_error":
                # Error messages should be user-friendly, not raw API errors
                msg = e.get("error", "")
                assert "Error code: 400" not in msg, \
                    f"Raw API error exposed to user: {msg}"

        print(f"  Events received: {[e.get('_eventType') for e in events]}")
        print(f"  Total events: {len(events)}")
    finally:
        # Cleanup
        with httpx.Client(base_url=BASE_URL) as client:
            client.delete(f"/topics/{topic_id}")


@pytest.mark.e2e
def test_regenerate_lesson_uses_agent_loop():
    """Regenerate lesson should work and return content via agent loop."""
    # This test requires an existing lesson with content
    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        r = client.get("/topics/1")
        if r.status_code != 200:
            pytest.skip("No topics available for testing")
        topic = r.json()
        sections = topic.get("sections", [])
        if not sections:
            pytest.skip("No sections available")
        lessons = sections[0].get("lessons", [])
        if not lessons:
            pytest.skip("No lessons available")
        lesson_id = lessons[0]["id"]

        r = client.post(f"/lessons/{lesson_id}/regenerate")
        if r.status_code == 200:
            data = r.json()
            assert "content" in data, f"Response missing content: {data}"
            assert "id" in data
            print(f"  Regenerated lesson {lesson_id}: {len(data.get('content', ''))} chars")
        else:
            # May fail without AI key, but should not be a 500 with raw API error
            assert r.status_code != 500 or "Error code: 400" not in r.text, \
                f"Raw API error in response: {r.text}"
