"""
Test suite for production security stack (JWT, rate limit, cost guard).

Run (server not required):
    python test_advanced.py
    python test_advanced.py --test rate-limit
"""
import argparse

from fastapi.testclient import TestClient

from app import app
from rate_limiter import rate_limiter_admin, rate_limiter_user

client = TestClient(app)


def get_token(username: str, password: str) -> str:
    r = client.post("/auth/token", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_jwt_flow():
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 401, r.text
    print("✓ /ask without token → 401")

    token = get_token("student", "demo123")
    r = client.post(
        "/ask",
        json={"question": "Explain JWT"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert "answer" in r.json()
    print("✓ JWT token → /ask returns 200")


def test_rate_limit():
    rate_limiter_user._windows.clear()
    token = get_token("student", "demo123")
    headers = {"Authorization": f"Bearer {token}"}
    statuses = []

    for i in range(12):
        r = client.post("/ask", json={"question": f"rate test {i}"}, headers=headers)
        statuses.append(r.status_code)

    assert statuses[:10].count(200) == 10, statuses
    assert 429 in statuses[10:], statuses
    print("✓ Rate limit: 10 OK then 429 for student")


def test_admin_higher_limit_and_stats():
    rate_limiter_admin._windows.clear()
    token = get_token("teacher", "teach456")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/admin/stats", headers=headers)
    assert r.status_code == 200, r.text
    print("✓ Admin can access /admin/stats")

    for i in range(15):
        r = client.post("/ask", json={"question": f"admin {i}"}, headers=headers)
        assert r.status_code == 200, f"admin request {i} failed: {r.status_code}"


    print("✓ Admin rate limit higher (15 requests OK)")


def test_cost_guard_usage():
    token = get_token("student", "demo123")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/me/usage", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "budget_usd" in data
    assert "cost_usd" in data
    print("✓ /me/usage returns budget info")


TESTS = {
    "jwt": test_jwt_flow,
    "rate-limit": test_rate_limit,
    "admin": test_admin_higher_limit_and_stats,
    "cost-guard": test_cost_guard_usage,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", choices=list(TESTS.keys()))
    args = parser.parse_args()

    if args.test:
        TESTS[args.test]()
        print(f"\nPassed: {args.test}")
    else:
        for name, fn in TESTS.items():
            fn()
        print("\nAll Part 4 production tests passed.")
