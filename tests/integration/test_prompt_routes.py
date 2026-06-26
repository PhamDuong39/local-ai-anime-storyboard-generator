import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.file_io import read_json
from app.main import app
from app.schemas.scene import SceneList
from app.services.project_service import ProjectService
from app.services.scene_service import SceneService
from app.web import routes_prompts


def _scene(status: str) -> dict[str, object]:
    return {
        "scene_id": "scene_001",
        "scene_number": 1,
        "title": "School gate",
        "source_excerpt": "Akira enters the school.",
        "summary": "Akira enters the empty school.",
        "characters": ["Akira"],
        "location": "school gate",
        "time_of_day": "dusk",
        "mood": "tense",
        "main_action": "Akira enters the gate",
        "camera_shot": "wide shot",
        "camera_angle": "eye level",
        "visual_details": ["rusted gate", "orange sky", "empty yard"],
        "continuity_notes": [],
        "status": status,
    }


def _configure(monkeypatch, tmp_path, status: str):
    settings = Settings(projects_root=tmp_path / "projects")
    monkeypatch.setattr(routes_prompts, "get_settings", lambda: settings)
    project = ProjectService(
        settings.projects_root,
        image_model_id=settings.image_model_id,
        low_vram_image_model_id=settings.low_vram_image_model_id,
    ).create_project("Prompt Route", "youtube_standard")
    scenes = SceneList.model_validate(
        {
            "project_id": project.project_id,
            "scene_count": 1,
            "scenes": [_scene(status)],
        }
    )
    SceneService(settings.projects_root).save_scenes(project.project_id, scenes)
    return settings, project


@pytest.mark.asyncio
async def test_prompt_generation_route_is_blocked_before_approval(
    monkeypatch, tmp_path
) -> None:
    settings, project = _configure(monkeypatch, tmp_path, "draft")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/prompts/generate",
            follow_redirects=False,
        )

    assert response.status_code == 409
    assert "SCENE_APPROVAL_REQUIRED" in response.text
    assert not (
        settings.projects_root / project.project_id / "metadata/prompts.json"
    ).exists()


@pytest.mark.asyncio
async def test_prompt_generation_route_succeeds_after_approval(
    monkeypatch, tmp_path
) -> None:
    settings, project = _configure(monkeypatch, tmp_path, "approved")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/prompts/generate",
            follow_redirects=False,
        )
        page = await client.get(f"/projects/{project.project_id}/prompts")

    assert response.status_code == 303
    assert response.headers["location"] == f"/projects/{project.project_id}/prompts"
    assert page.status_code == 200
    assert "anime storyboard illustration" in page.text
    root = settings.projects_root / project.project_id
    assert (
        read_json(root / "metadata/prompts.json")["prompts"][0]["scene_id"]
        == "scene_001"
    )
    assert read_json(root / "metadata/project.json")["status"] == "PROMPTS_GENERATED"


@pytest.mark.asyncio
async def test_prompt_page_renders_approved_scene_without_prompts(
    monkeypatch, tmp_path
) -> None:
    _, project = _configure(monkeypatch, tmp_path, "approved")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/projects/{project.project_id}/prompts")

    assert response.status_code == 200
    assert "1 approved scene" in response.text
    assert "No prompt has been generated" in response.text


@pytest.mark.asyncio
async def test_update_prompt_route_saves_manual_edit(monkeypatch, tmp_path) -> None:
    settings, project = _configure(monkeypatch, tmp_path, "approved")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            f"/projects/{project.project_id}/prompts/generate",
            follow_redirects=False,
        )
        response = await client.post(
            f"/projects/{project.project_id}/prompts/scene_001",
            data={
                "positive_prompt": "edited anime storyboard prompt",
                "negative_prompt": "text, subtitle, watermark",
            },
            headers={"HX-Request": "true"},
        )
        page = await client.get(f"/projects/{project.project_id}/prompts")

    assert response.status_code == 200
    assert "Prompt saved." in response.text
    assert "ready" in response.text
    assert "edited" in response.text
    assert "edited anime storyboard prompt" in page.text
    root = settings.projects_root / project.project_id
    saved_prompt = read_json(root / "metadata/prompts.json")["prompts"][0]
    assert saved_prompt["manual_edit"] is True
    assert saved_prompt["positive_prompt"] == "edited anime storyboard prompt"


@pytest.mark.asyncio
async def test_update_prompt_route_rejects_empty_prompt(monkeypatch, tmp_path) -> None:
    settings, project = _configure(monkeypatch, tmp_path, "approved")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            f"/projects/{project.project_id}/prompts/generate",
            follow_redirects=False,
        )
        response = await client.post(
            f"/projects/{project.project_id}/prompts/scene_001",
            data={
                "positive_prompt": "   ",
                "negative_prompt": "text, subtitle, watermark",
            },
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 400
    assert "PROMPT_UPDATE_INVALID" in response.text
    root = settings.projects_root / project.project_id
    saved_prompt = read_json(root / "metadata/prompts.json")["prompts"][0]
    assert saved_prompt["manual_edit"] is False
    assert saved_prompt["positive_prompt"].startswith("anime storyboard illustration")


@pytest.mark.asyncio
async def test_prompt_page_links_to_generation_when_prompts_are_ready(
    monkeypatch, tmp_path
) -> None:
    _, project = _configure(monkeypatch, tmp_path, "approved")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            f"/projects/{project.project_id}/prompts/generate",
            follow_redirects=False,
        )
        response = await client.get(f"/projects/{project.project_id}/prompts")

    assert response.status_code == 200
    assert f"/projects/{project.project_id}/generation" in response.text
