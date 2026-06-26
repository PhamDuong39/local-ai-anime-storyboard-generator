import pytest

from app.core.errors import AppError
from app.core.file_io import read_json, write_json
from app.schemas.character import CharacterMetadata, CharacterReference, CharacterStatus
from app.schemas.project import ProjectStatus
from app.schemas.prompt import PromptStatus
from app.schemas.scene import SceneList
from app.services.openai_prompt_service import (
    DEFAULT_NEGATIVE_PROMPT,
    OpenAIPromptService,
    PromptOpenAIResponse,
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


class FakePromptClient:
    def __init__(self, response: PromptOpenAIResponse) -> None:
        self.response = response

    def parse_json(self, **kwargs):
        assert kwargs["response_model"] is PromptOpenAIResponse
        return self.response


class FailingPromptClient:
    def parse_json(self, **kwargs):
        raise AppError(
            code="PROMPT_GENERATION_FAILED",
            message="OpenAI failed.",
            http_status=502,
        )


def _add_character(root, project_id: str) -> None:
    characters = CharacterMetadata(
        characters=[
            CharacterReference(
                name="Akira",
                original_filename="Akira.png",
                stored_path="input/characters/Akira.png",
                mime_type="image/png",
                width=1024,
                height=1536,
                file_size_bytes=100,
                status=CharacterStatus.VALID,
            )
        ]
    )
    write_json(root / project_id / "metadata/characters.json", characters)


def _prompt_response(project_id: str) -> PromptOpenAIResponse:
    return PromptOpenAIResponse.model_validate(
        {
            "project_id": project_id,
            "prompts": [
                {
                    "scene_id": "scene_001",
                    "scene_number": 1,
                    "positive_prompt": "anime storyboard, Akira at the school gate",
                    "negative_prompt": "text, subtitle, speech bubble, watermark",
                    "characters": [
                        {
                            "name": "Akira",
                            "role_in_scene": "main character",
                            "visual_priority": "high",
                        }
                    ],
                    "status": "ready",
                }
            ],
        }
    )


def test_real_prompt_generation_with_fake_client_persists_ready_prompt(
    tmp_path,
) -> None:
    root, project = _setup(tmp_path)
    _add_character(root, project.project_id)

    result = OpenAIPromptService(
        root,
        mock_mode=False,
        openai_client=FakePromptClient(_prompt_response(project.project_id)),
    ).generate_prompts(project.project_id)

    prompt = result.prompts[0]
    assert prompt.status is PromptStatus.READY
    assert prompt.generation_settings.num_images == 1
    assert prompt.generation_settings.num_inference_steps == 30
    assert prompt.generation_settings.guidance_scale == 7.0
    assert prompt.characters[0].consistency_method == "ip-adapter-faceid"
    assert (
        read_json(root / project.project_id / "metadata/project.json")["status"]
        == ProjectStatus.PROMPTS_GENERATED.value
    )


def test_real_prompt_generation_missing_scene_prompt_fails(tmp_path) -> None:
    root, project = _setup(tmp_path)
    response = PromptOpenAIResponse.model_validate(
        {
            "project_id": project.project_id,
            "prompts": [
                _prompt_response(project.project_id)
                .prompts[0]
                .model_copy(update={"scene_id": "scene_999"})
                .model_dump(mode="json")
            ],
        }
    )

    with pytest.raises(AppError) as caught:
        OpenAIPromptService(
            root,
            mock_mode=False,
            openai_client=FakePromptClient(response),
        ).generate_prompts(project.project_id)

    assert caught.value.code == "PROMPT_SCHEMA_INVALID"
    assert not (root / project.project_id / "metadata/prompts.json").exists()


def test_real_prompt_failure_preserves_existing_prompts(tmp_path) -> None:
    root, project = _setup(tmp_path)
    existing = OpenAIPromptService(root).generate_prompts(project.project_id)

    with pytest.raises(AppError) as caught:
        OpenAIPromptService(
            root,
            mock_mode=False,
            openai_client=FailingPromptClient(),
        ).generate_prompts(project.project_id)

    assert caught.value.code == "PROMPT_GENERATION_FAILED"
    assert read_json(
        root / project.project_id / "metadata/prompts.json"
    ) == existing.model_dump(mode="json")
    assert (
        read_json(root / project.project_id / "metadata/project.json")["status"]
        == ProjectStatus.PROMPT_GENERATION_FAILED.value
    )
