import pytest
from pydantic import ValidationError

from app.core.errors import AppError
from app.schemas.prompt import PromptList, PromptStatus
from app.schemas.scene import SceneList
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.scene_service import SceneService


def scene(scene_id: str, scene_number: int) -> dict[str, object]:
    return {
        "scene_id": scene_id,
        "scene_number": scene_number,
        "title": f"Scene {scene_number}",
        "source_excerpt": "Story excerpt",
        "summary": "A clear visual moment",
        "characters": ["Akira"],
        "location": "school",
        "time_of_day": "dusk",
        "mood": "tense",
        "main_action": "Akira enters",
        "camera_shot": "wide shot",
        "camera_angle": "eye level",
        "visual_details": ["rusted gate", "orange light", "empty yard"],
        "continuity_notes": [],
        "status": "approved",
    }


def prompt(scene_id: str, scene_number: int) -> dict[str, object]:
    return {
        "scene_id": scene_id,
        "scene_number": scene_number,
        "positive_prompt": f"anime storyboard scene {scene_number}",
        "negative_prompt": "text, subtitle, speech bubble, watermark, logo",
        "characters": [],
        "generation_settings": {"width": 1280, "height": 720},
        "status": "ready",
        "manual_edit": False,
    }


def setup_project(tmp_path) -> tuple[PromptService, str, dict[str, object]]:
    root = tmp_path / "projects"
    project = ProjectService(
        root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("Prompt Test", "youtube_standard")
    scenes = SceneList.model_validate(
        {
            "project_id": project.project_id,
            "scene_count": 2,
            "scenes": [scene("scene_001", 1), scene("scene_002", 2)],
        }
    )
    SceneService(root).save_scenes(project.project_id, scenes)
    return (
        PromptService(root),
        project.project_id,
        project.output_preset.model_dump(mode="json"),
    )


def make_prompt_list(project_id: str, preset: dict[str, object]) -> PromptList:
    return PromptList.model_validate(
        {
            "project_id": project_id,
            "output_preset": preset,
            "prompts": [prompt("scene_001", 1), prompt("scene_002", 2)],
        }
    )


def test_prompt_schema_rejects_blank_text_and_wrong_dimensions() -> None:
    data = {
        "project_id": "valid-project",
        "output_preset": {
            "id": "youtube_standard",
            "name": "YouTube Standard",
            "width": 1280,
            "height": 720,
            "aspect_ratio": "16:9",
        },
        "prompts": [prompt("scene_001", 1)],
    }
    data["prompts"][0]["positive_prompt"] = "   "
    with pytest.raises(ValidationError):
        PromptList.model_validate(data)

    data["prompts"][0]["positive_prompt"] = "anime storyboard"
    data["prompts"][0]["generation_settings"]["width"] = 1024
    with pytest.raises(ValidationError):
        PromptList.model_validate(data)


def test_prompt_list_round_trip_preserves_manual_edits(tmp_path) -> None:
    service, project_id, preset = setup_project(tmp_path)
    prompts = make_prompt_list(project_id, preset)
    prompts.prompts[0].positive_prompt = "hand-edited anime prompt"
    prompts.prompts[0].manual_edit = True

    service.save_prompts(project_id, prompts)
    loaded = service.get_prompts(project_id)

    assert loaded is not None
    assert loaded.prompts[0].positive_prompt == "hand-edited anime prompt"
    assert loaded.prompts[0].manual_edit is True


def test_prompt_scene_mapping_requires_one_prompt_per_approved_scene(tmp_path) -> None:
    service, project_id, preset = setup_project(tmp_path)
    prompts = make_prompt_list(project_id, preset)
    prompts.prompts.pop()

    with pytest.raises(AppError) as caught:
        service.save_prompts(project_id, prompts)

    assert caught.value.code == "PROMPT_SCHEMA_INVALID"


def test_stale_prompt_blocks_generation_readiness(tmp_path) -> None:
    service, project_id, preset = setup_project(tmp_path)
    prompts = make_prompt_list(project_id, preset)
    prompts.prompts[1].status = PromptStatus.STALE
    service.save_prompts(project_id, prompts)

    with pytest.raises(AppError) as caught:
        service.require_ready_prompts(project_id)

    assert caught.value.code == "PROMPT_STALE"


def test_update_prompt_marks_and_preserves_manual_edit(tmp_path) -> None:
    service, project_id, preset = setup_project(tmp_path)
    service.save_prompts(project_id, make_prompt_list(project_id, preset))

    updated = service.update_prompt(
        project_id,
        "scene_001",
        positive_prompt="  edited positive prompt  ",
        negative_prompt="  edited negative prompt  ",
    )

    assert updated.positive_prompt == "edited positive prompt"
    assert updated.manual_edit is True
    assert service.require_ready_prompts(project_id).prompts[0] == updated
