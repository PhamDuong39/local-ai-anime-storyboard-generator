import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.file_io import read_json
from app.main import app
from app.services.project_service import ProjectService
from app.services.story_service import StoryService
from app.web import routes_scenes


STORY = b"""# Episode One

Akira enters the empty school at dusk.

Hana warns him beside the dark hallway.

They hear footsteps approaching from a classroom."""


def configure_scene_project(monkeypatch, tmp_path):
    settings = Settings(projects_root=tmp_path / "projects")
    monkeypatch.setattr(routes_scenes, "get_settings", lambda: settings)
    project = ProjectService(
        settings.projects_root,
        image_model_id=settings.image_model_id,
        low_vram_image_model_id=settings.low_vram_image_model_id,
    ).create_project("Episode One", "youtube_standard")
    StoryService(settings.projects_root).save_story(
        project.project_id, "story.md", STORY
    )
    return settings, project


def configure_real_scene_project_without_key(monkeypatch, tmp_path):
    settings = Settings(projects_root=tmp_path / "projects", openai_mock_mode=False)
    monkeypatch.setattr(routes_scenes, "get_settings", lambda: settings)
    project = ProjectService(
        settings.projects_root,
        image_model_id=settings.image_model_id,
        low_vram_image_model_id=settings.low_vram_image_model_id,
    ).create_project("Episode One", "youtube_standard")
    StoryService(settings.projects_root).save_story(
        project.project_id, "story.md", STORY
    )
    return settings, project


async def split(client: AsyncClient, project_id: str) -> None:
    response = await client.post(
        f"/projects/{project_id}/scenes/split", follow_redirects=False
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_scene_page_shows_split_cta_and_mock_split_persists_drafts(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure_scene_project(monkeypatch, tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        page = await client.get(f"/projects/{project.project_id}/scenes")
        assert page.status_code == 200
        assert "Analyze Story and Split Scenes" in page.text

        await split(client, project.project_id)
        review = await client.get(f"/projects/{project.project_id}/scenes")

    assert "Story opening" in review.text
    assert "Approve scenes" in review.text
    root = settings.projects_root / project.project_id
    scenes = read_json(root / "metadata/scenes.json")
    assert scenes["scene_count"] == 3
    assert all(scene["status"] == "draft" for scene in scenes["scenes"])
    assert read_json(root / "metadata/project.json")["status"] == "SCENES_GENERATED"


@pytest.mark.asyncio
async def test_default_scene_route_uses_mock_data_without_api_key(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure_scene_project(monkeypatch, tmp_path)
    assert settings.openai_mock_mode is True
    assert settings.has_openai_api_key is False

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/scenes/split",
            follow_redirects=False,
        )

    assert response.status_code == 303
    scenes = read_json(
        settings.projects_root / project.project_id / "metadata/scenes.json"
    )
    assert scenes["scene_count"] == 3
    assert scenes["scenes"][0]["title"] == "Story opening"


@pytest.mark.asyncio
async def test_update_scene_returns_card_and_persists_edit(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure_scene_project(monkeypatch, tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await split(client, project.project_id)
        response = await client.post(
            f"/projects/{project.project_id}/scenes/scene_001",
            headers={"HX-Request": "true"},
            data={
                "title": "Akira reaches the gate",
                "summary": "Akira stops at the abandoned school gate.",
                "source_excerpt": "Akira enters the empty school at dusk.",
                "characters": "Akira",
                "location": "school gate",
                "time_of_day": "dusk",
                "mood": "uneasy",
                "main_action": "Akira stops at the gate",
                "camera_shot": "wide shot",
                "camera_angle": "low angle",
                "visual_details": "rusted gate\norange sky\nempty courtyard",
                "continuity_notes": "same outfit",
            },
        )

    assert response.status_code == 200
    assert response.text.lstrip().startswith('<article id="scene_001"')
    assert "Akira reaches the gate" in response.text
    scene = read_json(
        settings.projects_root / project.project_id / "metadata/scenes.json"
    )["scenes"][0]
    assert scene["title"] == "Akira reaches the gate"
    assert scene["status"] == "needs_edit"


@pytest.mark.asyncio
async def test_reorder_and_skip_return_updated_scene_list(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure_scene_project(monkeypatch, tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await split(client, project.project_id)
        reordered = await client.post(
            f"/projects/{project.project_id}/scenes/reorder",
            json={"scene_ids": ["scene_003", "scene_001", "scene_002"]},
        )
        skipped = await client.post(
            f"/projects/{project.project_id}/scenes/scene_001/skip"
        )

    assert reordered.status_code == 200
    assert reordered.text.lstrip().startswith('<section id="scene-list"')
    assert skipped.status_code == 200
    data = read_json(
        settings.projects_root / project.project_id / "metadata/scenes.json"
    )
    assert [scene["scene_id"] for scene in data["scenes"]] == [
        "scene_003",
        "scene_001",
        "scene_002",
    ]
    assert data["scenes"][1]["status"] == "skipped"
    assert [
        scene["scene_number"]
        for scene in data["scenes"]
        if scene["status"] != "skipped"
    ] == [1, 2]


@pytest.mark.asyncio
async def test_skip_last_active_scene_is_blocked(monkeypatch, tmp_path) -> None:
    _, project = configure_scene_project(monkeypatch, tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await split(client, project.project_id)
        await client.post(f"/projects/{project.project_id}/scenes/scene_001/skip")
        await client.post(f"/projects/{project.project_id}/scenes/scene_002/skip")
        response = await client.post(
            f"/projects/{project.project_id}/scenes/scene_003/skip"
        )

    assert response.status_code == 400
    assert "Keep at least one active scene" in response.text
    assert "SCENE_SKIP_INVALID" in response.text


@pytest.mark.asyncio
async def test_approve_scenes_updates_status_and_redirects(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure_scene_project(monkeypatch, tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await split(client, project.project_id)
        await client.post(f"/projects/{project.project_id}/scenes/scene_002/skip")
        response = await client.post(
            f"/projects/{project.project_id}/scenes/approve",
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == f"/projects/{project.project_id}/prompts"
    root = settings.projects_root / project.project_id
    data = read_json(root / "metadata/scenes.json")
    assert [scene["status"] for scene in data["scenes"]] == [
        "approved",
        "skipped",
        "approved",
    ]
    assert read_json(root / "metadata/project.json")["status"] == "SCENES_APPROVED"


@pytest.mark.asyncio
async def test_real_scene_route_without_api_key_returns_friendly_error(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure_real_scene_project_without_key(monkeypatch, tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/scenes/split",
            follow_redirects=False,
        )

    assert response.status_code == 503
    assert "OPENAI_API_KEY_MISSING" in response.text
    assert not (
        settings.projects_root / project.project_id / "metadata/scenes.json"
    ).exists()
