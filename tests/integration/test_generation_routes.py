from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.file_io import read_json, write_json
from app.core.paths import metadata_path, project_root
from app.main import app
from app.schemas.character import CharacterMetadata
from app.schemas.generation import HardwareDetection, HardwareProfile
from app.schemas.prompt import PromptList
from app.schemas.scene import SceneList
from app.services.generation_job_service import GenerationJobService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.scene_service import SceneService
from app.web import routes_generation


NOW = datetime(2026, 6, 11, 10, 15, 30, tzinfo=timezone.utc)


class FakeHardwareService:
    def detect_hardware(self) -> HardwareDetection:
        return HardwareDetection(
            device="cuda",
            gpu_name="High VRAM GPU",
            vram_gb=12,
            cuda_available=True,
            hardware_profile=HardwareProfile.HIGH_VRAM_12GB_PLUS,
            detected_at=NOW,
        )


def scene(status: str) -> dict[str, object]:
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


def prompt() -> dict[str, object]:
    return {
        "scene_id": "scene_001",
        "scene_number": 1,
        "positive_prompt": "anime storyboard illustration",
        "negative_prompt": "text, subtitle, watermark, logo",
        "characters": [
            {
                "name": "Akira",
                "reference_image_path": "input/characters/Akira.png",
                "consistency_method": "ip-adapter-faceid",
                "role_in_scene": "main character",
                "visual_priority": "high",
            }
        ],
        "generation_settings": {"width": 1280, "height": 720},
        "status": "ready",
    }


def configure(monkeypatch, tmp_path, scene_status: str):
    settings = Settings(projects_root=tmp_path / "projects")
    monkeypatch.setattr(routes_generation, "get_settings", lambda: settings)
    monkeypatch.setattr(
        routes_generation,
        "_generation_job_service",
        lambda active_settings: GenerationJobService(
            active_settings.projects_root,
            hardware_service=FakeHardwareService(),
        ),
    )
    project = ProjectService(
        settings.projects_root,
        image_model_id=settings.image_model_id,
        low_vram_image_model_id=settings.low_vram_image_model_id,
    ).create_project("Generation Route", "youtube_standard")
    SceneService(settings.projects_root).save_scenes(
        project.project_id,
        SceneList.model_validate(
            {
                "project_id": project.project_id,
                "scene_count": 1,
                "scenes": [scene(scene_status)],
            }
        ),
    )
    character_path = (
        project_root(settings.projects_root, project.project_id)
        / "input/characters/Akira.png"
    )
    character_path.write_bytes(b"reference")
    write_json(
        metadata_path(settings.projects_root, project.project_id, "characters.json"),
        CharacterMetadata.model_validate(
            {
                "characters": [
                    {
                        "name": "Akira",
                        "original_filename": "Akira.png",
                        "stored_path": "input/characters/Akira.png",
                        "mime_type": "image/png",
                        "width": 1024,
                        "height": 1536,
                        "file_size_bytes": 9,
                        "consistency_method": "ip-adapter-faceid",
                        "status": "valid",
                    }
                ]
            }
        ),
    )
    return settings, project


@pytest.mark.asyncio
async def test_start_generation_before_approval_returns_error(
    monkeypatch, tmp_path
) -> None:
    _, project = configure(monkeypatch, tmp_path, "draft")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/generation/start",
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SCENE_APPROVAL_REQUIRED"


@pytest.mark.asyncio
async def test_start_generation_with_valid_mock_data_succeeds(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure(monkeypatch, tmp_path, "approved")
    PromptService(settings.projects_root).save_prompts(
        project.project_id,
        PromptList.model_validate(
            {
                "project_id": project.project_id,
                "output_preset": project.output_preset.model_dump(mode="json"),
                "prompts": [prompt()],
            }
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/projects/{project.project_id}/generation/start",
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["job"]["status"] == "completed"
    assert body["data"]["job"]["total_scenes"] == 1
    root = settings.projects_root / project.project_id
    assert read_json(root / "metadata/generation_status.json")["status"] == "completed"
    manifest = read_json(root / "outputs/manifest.json")
    assert manifest["assets"][0]["scene_id"] == "scene_001"
    assert (root / manifest["assets"][0]["output_path"]).is_file()


@pytest.mark.asyncio
async def test_generation_page_shows_readiness_without_start_button_when_blocked(
    monkeypatch, tmp_path
) -> None:
    _, project = configure(monkeypatch, tmp_path, "draft")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/projects/{project.project_id}/generation")

    assert response.status_code == 200
    assert "Readiness" in response.text
    assert "SCENE_APPROVAL_REQUIRED" in response.text
    assert "Generate images" not in response.text


@pytest.mark.asyncio
async def test_generation_page_shows_start_button_when_ready(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure(monkeypatch, tmp_path, "approved")
    PromptService(settings.projects_root).save_prompts(
        project.project_id,
        PromptList.model_validate(
            {
                "project_id": project.project_id,
                "output_preset": project.output_preset.model_dump(mode="json"),
                "prompts": [prompt()],
            }
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/projects/{project.project_id}/generation")

    assert response.status_code == 200
    assert "Ready" in response.text
    assert "High VRAM GPU" in response.text
    assert "Available" in response.text
    assert "12.0 GB" in response.text
    assert "Generate images" in response.text


@pytest.mark.asyncio
async def test_generation_status_polling_renders_for_running_status(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure(monkeypatch, tmp_path, "approved")
    PromptService(settings.projects_root).save_prompts(
        project.project_id,
        PromptList.model_validate(
            {
                "project_id": project.project_id,
                "output_preset": project.output_preset.model_dump(mode="json"),
                "prompts": [prompt()],
            }
        ),
    )
    job_service = GenerationJobService(
        settings.projects_root,
        hardware_service=FakeHardwareService(),
    )
    job_service.start_job(project.project_id)
    job_service.mark_running(
        project.project_id,
        scene_id="scene_001",
        scene_number=1,
        scene_title="School gate",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/projects/{project.project_id}/generation/status",
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert 'hx-trigger="every 2s"' in response.text
    assert "running" in response.text


@pytest.mark.asyncio
async def test_generation_status_terminal_state_stops_polling(
    monkeypatch, tmp_path
) -> None:
    settings, project = configure(monkeypatch, tmp_path, "approved")
    PromptService(settings.projects_root).save_prompts(
        project.project_id,
        PromptList.model_validate(
            {
                "project_id": project.project_id,
                "output_preset": project.output_preset.model_dump(mode="json"),
                "prompts": [prompt()],
            }
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            f"/projects/{project.project_id}/generation/start",
            headers={"Accept": "application/json"},
        )
        response = await client.get(
            f"/projects/{project.project_id}/generation/status",
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert 'hx-trigger="every 2s"' not in response.text
    assert "completed" in response.text


@pytest.mark.asyncio
async def test_generation_status_json_response(monkeypatch, tmp_path) -> None:
    settings, project = configure(monkeypatch, tmp_path, "approved")
    PromptService(settings.projects_root).save_prompts(
        project.project_id,
        PromptList.model_validate(
            {
                "project_id": project.project_id,
                "output_preset": project.output_preset.model_dump(mode="json"),
                "prompts": [prompt()],
            }
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            f"/projects/{project.project_id}/generation/start",
            headers={"Accept": "application/json"},
        )
        response = await client.get(
            f"/projects/{project.project_id}/generation/status",
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "completed"
