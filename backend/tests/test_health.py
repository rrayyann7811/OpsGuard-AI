from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["database"] == "connected"


def test_allowed_origin():
    response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_origin():
    response = client.get("/api/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_database_unavailable():
    with patch("app.main.engine.connect", side_effect=OperationalError("SELECT 1", {}, Exception("unavailable"))):
        response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_unknown_route():
    assert client.get("/api/missing").status_code == 404


def test_api_schema():
    assert "/api/health" in client.get("/openapi.json").json()["paths"]


def test_cors_preflight():
    response = client.options("/api/health", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unhandled_error_hides_details():
    with patch("app.main.engine.connect", side_effect=RuntimeError("private internals")):
        response = TestClient(app, raise_server_exceptions=False).get("/api/health")
    assert response.status_code == 500
    assert response.json() == {"detail": "An unexpected error occurred"}
