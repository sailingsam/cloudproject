"""Tests for the operational endpoints added for Kubernetes and monitoring."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz_ok(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["database"] == "up"


def test_readyz_db_down(client):
    with patch("app.main.ping", side_effect=ConnectionError("db down")):
        r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["database"] == "down"


def test_liveness_ignores_db(client):
    # A database outage must not fail liveness, or Kubernetes would restart
    # every app pod for a problem a restart cannot fix.
    with patch("app.main.ping", side_effect=ConnectionError("db down")):
        assert client.get("/healthz").status_code == 200


def test_ops_routes_not_shadowed_by_redirect(client):
    # "/{code}" is a catch-all; operational paths must still reach their handlers.
    for path in ("/healthz", "/version", "/metrics"):
        assert client.get(path, follow_redirects=False).status_code == 200


def test_version(client):
    body = client.get("/version").json()
    assert set(body) >= {"version", "git_sha", "build_date"}


def test_version_header(client):
    assert "x-app-version" in client.get("/healthz").headers


def test_request_id_propagated(client):
    r = client.get("/api/links", headers={"x-request-id": "abc123"})
    assert r.headers["x-request-id"] == "abc123"


def test_metrics_use_route_templates(client):
    code = client.post("/api/links", json={"url": "https://example.com"}).json()["code"]
    client.get(f"/{code}", follow_redirects=False)
    client.get("/nope-404", follow_redirects=False)
    text = client.get("/metrics").text
    assert 'route="/{code}"' in text
    assert f'route="/{code}"' not in text
    assert "http_request_duration_seconds_bucket" in text
    assert 'links_operations_total{operation="redirect",outcome="success"}' in text
    assert 'links_operations_total{operation="redirect",outcome="not_found"}' in text
    assert "links_app_build_info" in text


def test_unmatched_route_label(client):
    client.post("/api/does-not-exist")
    assert 'route="unmatched"' in client.get("/metrics").text
