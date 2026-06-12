"""
Test API Key authentication for develop/app.py.

Run (server not required):
    AGENT_API_KEY=my-secret-key python test_auth.py
"""
import os

from fastapi.testclient import TestClient

os.environ.setdefault("AGENT_API_KEY", "my-secret-key")

from app import app  # noqa: E402

client = TestClient(app)
API_KEY = os.environ["AGENT_API_KEY"]
PAYLOAD = {"question": "Hello"}


def test_no_key_returns_401():
    r = client.post("/ask", json=PAYLOAD)
    assert r.status_code == 401, r.text
    print("✓ No API key → 401")


def test_wrong_key_returns_403():
    r = client.post("/ask", json=PAYLOAD, headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 403, r.text
    print("✓ Wrong API key → 403")


def test_valid_key_returns_200():
    r = client.post("/ask", json=PAYLOAD, headers={"X-API-Key": API_KEY})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["question"] == "Hello"
    assert "answer" in data
    print("✓ Valid API key → 200")


def test_health_is_public():
    r = client.get("/health")
    assert r.status_code == 200, r.text
    print("✓ /health is public → 200")


if __name__ == "__main__":
    test_health_is_public()
    test_no_key_returns_401()
    test_wrong_key_returns_403()
    test_valid_key_returns_200()
    print("\nAll auth tests passed.")
