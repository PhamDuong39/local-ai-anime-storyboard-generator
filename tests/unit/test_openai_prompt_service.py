import pytest

from app.core.errors import AppError
from app.core.file_io import read_json
from app.schemas.scene import SceneList
from app.services.openai_prompt_service import (
    DEFAULT_NEGATIVE_PROMPT,
    OpenAIPromptService,
)
from app.services.project_service import ProjectService
from app.services.scene_service import SceneService


def _scene(status: str = "approved") -> dict[str, object]:
    return {
        "scene_id": "scene_001",
        "scene_number": 1,
        "title": "Akira enters school",
        "source_excerpt": "Akira enters the empty school at dusk.",
        "summary": "Akira enters an empty school.",
        "characters": ["Akira"],
        "location": "empty school",
        "time_of_day": "dusk",
        "mood": "tense",
        "main_action": "Akira enters through the gate",
        "camera_shot": "wide shot",
        "camera_angle": "eye level",
        "visual_details": ["rusted gate", "orange sky", "empty courtyard"],
        "continuity_notes": ["keep Akira's school uniform consistent"],
        "status": status,
    }


def _setup(tmp_path, status: str = "approved"):
    root = tmp_path / "projects"
    project = ProjectService(
        root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("Prompt Mock", "youtube_standard")
    scenes = SceneList.model_validate(
        {
            "project_id": project.project_id,
            "scene_count": 1,
            "scenes": [_scene(status)],
        }
    )
    SceneService(root).save_scenes(project.project_id, scenes)
    return root, project


def test_mock_prompt_output_validates_and_is_persisted(tmp_path) -> None:
    root, project = _setup(tmp_path)

    result = OpenAIPromptService(root).generate_prompts(project.project_id)

    assert len(result.prompts) == 1
    prompt = result.prompts[0]
    assert "anime storyboard illustration" in prompt.positive_prompt
    assert "Akira" in prompt.positive_prompt
    assert "1280x720 output" in prompt.positive_prompt
    assert prompt.negative_prompt == DEFAULT_NEGATIVE_PROMPT
    assert prompt.generation_settings.width == 1280
    assert prompt.generation_settings.height == 720
    assert prompt.generation_settings.num_images == 1
    assert prompt.generation_settings.num_inference_steps == 30
    assert prompt.generation_settings.guidance_scale == 7.0
    assert (
        read_json(root / project.project_id / "metadata/prompts.json")["prompts"][0][
            "status"
        ]
        == "ready"
    )
    assert (
        read_json(root / project.project_id / "metadata/project.json")["status"]
        == "PROMPTS_GENERATED"
    )


def test_mock_prompt_generation_requires_approved_scenes(tmp_path) -> None:
    root, project = _setup(tmp_path, status="draft")

    with pytest.raises(AppError) as caught:
        OpenAIPromptService(root).generate_prompts(project.project_id)

    assert caught.value.code == "SCENE_APPROVAL_REQUIRED"
    assert not (root / project.project_id / "metadata/prompts.json").exists()
