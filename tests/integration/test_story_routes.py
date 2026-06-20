import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.file_io import read_json
from app.main import app
from app.services.project_service import ProjectService
from app.web import routes_story


def configure_story_project(monkeypatch, tmp_path):
    settings = Settings(projects_root=tmp_path / "projects")
    monkeypatch.setattr(routes_story, "get_settings", lambda: settings)
    project = ProjectService(
        settings.projects_root,
        image_model_id=settings.image_model_id,
        low_vram_image_model_id=settings.low_vram_image_model_id,
    ).create_project("Akira Episode 1", "youtube_standard")
    return settings, project


@pytest.mark.asyncio
async def test_get_story_page_shows_free_form_upload(monkeypatch, tmp_path) -> None:
    _, project = configure_story_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/projects/{project.project_id}/story")

    assert response.status_code == 200
    assert "no scene tags or special formatting are required" in response.text
    assert 'name="story_file"' in response.text
    assert 'accept=".md,text/markdown,text/plain"' in response.text


@pytest.mark.asyncio
async def test_upload_valid_story_redirects_and_saves_metadata(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure_story_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/story",
            files={
                "story_file": (
                    "episode.md",
                    "# Episode 1\n\nAkira enters the school.",
                    "text/markdown",
                )
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/projects/{project.project_id}/characters"
    )
    root = settings.projects_root / project.project_id
    assert (
        (root / "input/story.md").read_text(encoding="utf-8").startswith("# Episode 1")
    )
    story = read_json(root / "metadata/story.json")
    project_data = read_json(root / "metadata/project.json")
    assert story["story_char_count"] == 37
    assert story["approx_word_count"] == 7
    assert project_data["status"] == "STORY_UPLOADED"


@pytest.mark.asyncio
async def test_upload_unsupported_file_type_shows_friendly_error(
    monkeypatch, tmp_path
) -> None:
    _, project = configure_story_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/story",
            files={"story_file": ("episode.txt", "Akira enters.", "text/plain")},
        )

    assert response.status_code == 400
    assert "Please upload a Markdown .md story file." in response.text
    assert "STORY_UNSUPPORTED_FILE_TYPE" in response.text
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_upload_empty_story_shows_friendly_error(monkeypatch, tmp_path) -> None:
    _, project = configure_story_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/story",
            files={"story_file": ("episode.md", "  \n\t", "text/markdown")},
        )

    assert response.status_code == 400
    assert "Your story file is empty." in response.text
    assert "STORY_EMPTY" in response.text
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_htmx_upload_returns_validation_partial_with_preview(
    monkeypatch, tmp_path
) -> None:
    _, project = configure_story_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/story",
            headers={"HX-Request": "true"},
            files={
                "story_file": (
                    "episode.md",
                    "Akira enters.\nHana waves.",
                    "text/markdown",
                )
            },
        )

    assert response.status_code == 200
    assert response.text.lstrip().startswith('<section id="story-validation"')
    assert "Story uploaded and validated successfully." in response.text
    assert "Akira enters." in response.text
    assert "Continue to Character Upload" in response.text
    assert "<html" not in response.text


@pytest.mark.asyncio
async def test_story_page_shows_existing_story_preview(monkeypatch, tmp_path) -> None:
    _, project = configure_story_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            f"/projects/{project.project_id}/story",
            files={
                "story_file": (
                    "episode.md",
                    "Akira enters the moonlit hallway.",
                    "text/markdown",
                )
            },
        )
        response = await client.get(f"/projects/{project.project_id}/story")

    assert response.status_code == 200
    assert "Akira enters the moonlit hallway." in response.text
    assert "episode.md" in response.text
    assert "characters" in response.text
