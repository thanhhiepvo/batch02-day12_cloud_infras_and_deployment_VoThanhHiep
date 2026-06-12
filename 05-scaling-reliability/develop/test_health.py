"""
Test health/readiness endpoints for develop/app.py.

Run: python test_health.py
"""
from fastapi.testclient import TestClient

from app import app


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] in ("ok", "degraded")
    assert "uptime_seconds" in data
    print("✓ GET /health → 200")


def test_ready_returns_ok_when_started(client):
    r = client.get("/ready")
    assert r.status_code == 200, r.text
    assert r.json()["ready"] is True
    print("✓ GET /ready → 200")


def test_ask_requires_json_body(client):
    r = client.post("/ask", json={"question": "hello"})
    assert r.status_code == 200, r.text
    assert "answer" in r.json()
    print("✓ POST /ask with JSON body → 200")


if __name__ == "__main__":
    with TestClient(app) as client:
        test_health_returns_ok(client)
        test_ready_returns_ok_when_started(client)
        test_ask_requires_json_body(client)
    print("\nAll Part 5 develop tests passed.")
