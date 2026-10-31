import os

# Must be set before the app is imported: SQLite in memory, in-memory Mongo/Redis fallbacks.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["MONGO_URL"] = ""
os.environ["REDIS_URL"] = ""
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["JWT_SECRET"] = "test-secret-key-for-pytest-only-32b"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # runs lifespan: creates tables + seeds demo data
        yield c


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.fixture()
def demo_headers(client):
    return login(client, "demo@bank.com", "Demo@1234")


@pytest.fixture()
def admin_headers(client):
    return login(client, "admin@bank.com", "Admin@1234")
