"""
End-to-end tests for Part 6 — production agent.

Prerequisites:
  docker compose up -d --scale agent=3 --build

Run:
  python test_lab_complete.py
"""
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost"
API_KEY = "lab-complete-secret-key"


def request(method: str, path: str, data: dict | None = None, api_key: str | None = API_KEY):
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["X-API-Key"] = api_key
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_health_and_ready():
    status, health = request("GET", "/health", api_key=None)
    assert status == 200, health
    assert health["status"] in ("ok", "degraded")

    status, ready = request("GET", "/ready", api_key=None)
    assert status == 200, ready
    assert ready["ready"] is True
    print("✅ /health and /ready")


def test_auth_required():
    status, _ = request("POST", "/ask", {"question": "Hello"}, api_key=None)
    assert status == 401
    print("✅ Auth required (401 without API key)")


def test_conversation_history():
    status, first = request("POST", "/ask", {"question": "What is Docker?"})
    assert status == 200, first
    session_id = first["session_id"]
    assert first["turn"] == 1

    status, second = request("POST", "/ask", {
        "question": "Why use containers?",
        "session_id": session_id,
    })
    assert status == 200, second
    assert second["session_id"] == session_id
    assert second["history_count"] >= 4

    status, history = request("GET", f"/ask/{session_id}/history")
    assert status == 200, history
    assert history["count"] >= 4
    print(f"✅ Conversation history ({history['count']} messages, session={session_id[:8]}...)")


def test_stateless_scaling():
    instances = set()
    session_id = None
    for i in range(5):
        payload = {"question": f"Question {i+1} about deployment"}
        if session_id:
            payload["session_id"] = session_id
        status, result = request("POST", "/ask", payload)
        assert status == 200, result
        session_id = result["session_id"]
        instances.add(result["served_by"])

    print(f"✅ Stateless scaling — instances seen: {instances}")
    if len(instances) > 1:
        print("   Load balancing across multiple agent containers confirmed")
    else:
        print("   ℹ️  Only 1 instance — run: docker compose up -d --scale agent=3")


def test_rate_limit():
    # Prior tests already consumed some quota; send enough to exceed 10/min limit.
    for i in range(15):
        status, body = request("POST", "/ask", {"question": f"rate test {i}"})
        if status == 429:
            print(f"✅ Rate limiting triggered at request {i + 1}")
            return
    print("⚠️  Rate limit not hit — wait 60s and rerun if needed")


if __name__ == "__main__":
    print("=" * 60)
    print("Part 6 — Production Agent Tests")
    print("=" * 60)
    test_health_and_ready()
    test_auth_required()
    test_conversation_history()
    test_stateless_scaling()
    test_rate_limit()
    print("\n🎉 Part 6 local tests completed!")
