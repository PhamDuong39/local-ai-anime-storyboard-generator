from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.config import Settings
from app.core.file_io import read_json
from app.main import app
from app.services.project_service import ProjectService
from app.web import routes_characters


def configure_character_project(monkeypatch, tmp_path):
    settings = Settings(projects_root=tmp_path / "projects")
    monkeypatch.setattr(routes_characters, "get_settings", lambda: settings)
    project = ProjectService(
        settings.projects_root,
        image_model_id=settings.image_model_id,
        low_vram_image_model_id=settings.low_vram_image_model_id,
    ).create_project("Akira Episode 1", "youtube_standard")
    return settings, project


def image_bytes(image_format: str = "PNG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (768, 1024), color="navy").save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_get_character_page_shows_upload_guidance(monkeypatch, tmp_path) -> None:
    _, project = configure_character_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/projects/{project.project_id}/characters")

    assert response.status_code == 200
    assert "one full-body image for each main character" in response.text
    assert "Results are best-effort" in response.text
    assert 'name="character_files"' in response.text
    assert "multiple" in response.text


@pytest.mark.asyncio
async def test_valid_character_upload_redirects_and_saves_metadata(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure_character_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/characters",
            files=[
                ("character_files", ("Akira.png", image_bytes(), "image/png")),
                ("character_files", ("Hana.jpg", image_bytes("JPEG"), "image/jpeg")),
            ],
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == f"/projects/{project.project_id}/scenes"
    root = settings.projects_root / project.project_id
    metadata = read_json(root / "metadata/characters.json")
    assert [character["name"] for character in metadata["characters"]] == [
        "Akira",
        "Hana",
    ]
    assert metadata["characters"][0]["stored_path"] == (
        "input/characters/Akira.png"
    )
    assert read_json(root / "metadata/project.json")["status"] == (
        "CHARACTERS_UPLOADED"
    )


@pytest.mark.asyncio
async def test_duplicate_character_upload_shows_friendly_error(
    monkeypatch, tmp_path
) -> None:
    _, project = configure_character_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/characters",
            files=[
                ("character_files", ("Akira.png", image_bytes(), "image/png")),
                ("character_files", ("akira.jpg", image_bytes("JPEG"), "image/jpeg")),
            ],
        )

    assert response.status_code == 400
    assert "Please keep only one image for each character." in response.text
    assert "DUPLICATE_CHARACTER_NAME" in response.text
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_unsupported_character_extension_shows_friendly_error(
    monkeypatch, tmp_path
) -> None:
    _, project = configure_character_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/characters",
            files={"character_files": ("Akira.gif", b"image", "image/gif")},
        )

    assert response.status_code == 400
    assert "Please upload a PNG, JPG, JPEG, or WEBP image." in response.text
    assert "UNSUPPORTED_CHARACTER_IMAGE_TYPE" in response.text


@pytest.mark.asyncio
async def test_missing_character_files_shows_friendly_error(
    monkeypatch, tmp_path
) -> None:
    _, project = configure_character_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(f"/projects/{project.project_id}/characters")

    assert response.status_code == 400
    assert "Choose at least one character reference image" in response.text
    assert "CHARACTER_FILE_REQUIRED" in response.text


@pytest.mark.asyncio
async def test_htmx_upload_returns_character_validation_partial(
    monkeypatch, tmp_path
) -> None:
    _, project = configure_character_project(monkeypatch, tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/characters",
            headers={"HX-Request": "true"},
            files={"character_files": ("Akira.png", image_bytes(), "image/png")},
        )

    assert response.status_code == 200
    assert response.text.lstrip().startswith('<section id="character-validation"')
    assert "Character images uploaded and validated successfully." in response.text
    assert "Akira" in response.text
    assert "Continue to Scene Review" in response.text
    assert "<html" not in response.text
