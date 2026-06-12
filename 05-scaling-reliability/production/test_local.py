"""
Test stateless session logic locally (no Docker required).

Run: python test_local.py
"""
from fastapi.testclient import TestClient

from app import app, USE_REDIS


def test_chat_session_persists(client):
    r1 = client.post("/chat", json={"question": "What is Docker?"})
    assert r1.status_code == 200, r1.text
    session_id = r1.json()["session_id"]

    r2 = client.post("/chat", json={"question": "Why containers?", "session_id": session_id})
    assert r2.status_code == 200, r2.text
    assert r2.json()["turn"] >= 2

    history = client.get(f"/chat/{session_id}/history")
    assert history.status_code == 200
    assert history.json()["count"] >= 4
    print(f"✓ Session persists across requests (storage: {'redis' if USE_REDIS else 'in-memory'})")


def test_health_and_ready(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    print("✓ /health and /ready → 200")


if __name__ == "__main__":
    with TestClient(app) as client:
        test_health_and_ready(client)
        test_chat_session_persists(client)
    print("\nAll Part 5 production local tests passed.")
