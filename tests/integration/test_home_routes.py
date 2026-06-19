from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_home_returns_html() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Local AI Anime Storyboard Generator" in response.text


def test_get_health_returns_expected_json() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "status": "healthy",
        "app": "local-ai-anime-storyboard-generator",
    }
