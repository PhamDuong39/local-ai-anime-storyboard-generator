import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.web import routes_projects


def configure_projects_root(monkeypatch, tmp_path) -> None:
    settings = Settings(projects_root=tmp_path / "projects")
    monkeypatch.setattr(routes_projects, "get_settings", lambda: settings)


@pytest.mark.asyncio
async def test_get_new_project_form(monkeypatch, tmp_path) -> None:
    configure_projects_root(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/projects/new")

    assert response.status_code == 200
    assert 'value="youtube_standard"' in response.text
    assert "Create a new project" in response.text


@pytest.mark.asyncio
async def test_post_projects_creates_project_and_redirects_to_story(
    monkeypatch, tmp_path
) -> None:
    configure_projects_root(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/projects",
            data={
                "project_name": "Akira Episode 1",
                "output_preset": "youtube_standard",
                "description": "Opening episode",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/projects/akira-episode-1-")
    project_id = response.headers["location"].split("/")[2]
    assert (tmp_path / "projects" / project_id / "metadata/project.json").is_file()


@pytest.mark.asyncio
async def test_post_projects_shows_invalid_name_error(monkeypatch, tmp_path) -> None:
    configure_projects_root(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/projects",
            data={"project_name": "", "output_preset": "youtube_standard"},
        )

    assert response.status_code == 422
    assert "Enter a project name to continue." in response.text
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_get_project_dashboard(monkeypatch, tmp_path) -> None:
    configure_projects_root(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_response = await client.post(
            "/projects",
            data={"project_name": "Akira", "output_preset": "low_vram_preview"},
            follow_redirects=False,
        )
        project_id = create_response.headers["location"].split("/")[2]
        response = await client.get(f"/projects/{project_id}")

    assert response.status_code == 200
    assert "Akira" in response.text
    assert "Low VRAM Preview" in response.text
