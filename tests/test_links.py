import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_create_and_redirect(client):
    r = client.post("/api/links", json={"url": "https://example.com/page"})
    assert r.status_code == 201
    code = r.json()["code"]
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com/page"


def test_click_counter(client):
    code = client.post("/api/links", json={"url": "https://example.com"}).json()["code"]
    for _ in range(3):
        client.get(f"/{code}", follow_redirects=False)
    assert client.get(f"/api/links/{code}").json()["clicks"] == 3


def test_custom_code_and_conflict(client):
    assert client.post("/api/links", json={"url": "https://a.com", "code": "mine"}).status_code == 201
    assert client.post("/api/links", json={"url": "https://b.com", "code": "mine"}).status_code == 409


def test_invalid_input(client):
    assert client.post("/api/links", json={"url": "not-a-url"}).status_code == 422
    assert client.post("/api/links", json={"url": "https://a.com", "code": "x"}).status_code == 422


def test_unknown_code(client):
    assert client.get("/nope123", follow_redirects=False).status_code == 404


def test_delete(client):
    code = client.post("/api/links", json={"url": "https://example.com"}).json()["code"]
    assert client.delete(f"/api/links/{code}").status_code == 204
    assert client.get(f"/api/links/{code}").status_code == 404
