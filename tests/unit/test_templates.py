from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_home_template_renders_with_base_assets() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "/static/css/app.css" in response.text
    assert "/static/vendor/htmx/htmx.min.js" in response.text
    assert "No active messages." in response.text
