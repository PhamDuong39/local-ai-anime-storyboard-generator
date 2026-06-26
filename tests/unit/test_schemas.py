from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.schemas.character import CharacterMetadata
from app.schemas.generation import GenerationSettings, HardwareProfile
from app.schemas.jobs import GenerationJob
from app.schemas.manifest import OutputManifest
from app.schemas.project import OutputPreset, ProjectMetadata
from app.schemas.prompt import PromptList, PromptStatus
from app.schemas.scene import SceneList, SceneStatus
from app.schemas.story import StoryMetadata


NOW = "2026-06-11T10:15:30Z"
PRESET = {
    "id": "youtube_standard",
    "name": "YouTube Standard",
    "width": 1280,
    "height": 720,
    "aspect_ratio": "16:9",
}
SCENE = {
    "scene_id": "scene_001",
    "scene_number": 1,
    "title": "Akira enters the school",
    "source_excerpt": "Akira stepped through the rusted gate.",
    "summary": "Akira enters an abandoned school at dusk.",
    "characters": ["Akira"],
    "location": "abandoned school gate",
    "time_of_day": "dusk",
    "mood": "tense",
    "main_action": "Akira walks through the gate",
    "camera_shot": "wide shot",
    "camera_angle": "low angle",
    "visual_details": ["rusted gate", "orange light", "empty courtyard"],
    "continuity_notes": ["same outfit"],
    "status": "draft",
}
PROMPT_CHARACTER = {
    "name": "Akira",
    "reference_image_path": "input/characters/Akira.png",
    "consistency_method": "ip-adapter-faceid",
    "role_in_scene": "main character",
    "visual_priority": "high",
}


def test_project_and_output_preset_schemas() -> None:
    project = ProjectMetadata.model_validate(
        {
            "project_id": "akira-episode-1-a7f3c2",
            "project_name": "Akira Episode 1",
            "status": "CREATED",
            "output_preset": PRESET,
            "created_at": NOW,
            "updated_at": NOW,
        }
    )

    assert project.version == 1
    assert project.output_preset.id.value == "youtube_standard"


def test_legacy_output_preset_id_is_rejected() -> None:
    legacy = {**PRESET, "id": "youtube_standard_720p"}

    with pytest.raises(ValidationError):
        OutputPreset.model_validate(legacy)


def test_story_schema_accepts_documented_legacy_count_but_serializes_canonical_name() -> (
    None
):
    story = StoryMetadata.model_validate(
        {
            "story_status": "UPLOADED",
            "original_filename": "story.md",
            "stored_path": "input/story.md",
            "file_size_bytes": 100,
            "character_count": 80,
            "approx_word_count": 12,
            "line_count": 4,
            "uploaded_at": NOW,
            "content_hash": f"sha256:{'a' * 64}",
        }
    )

    assert story.story_char_count == 80
    assert "story_char_count" in story.model_dump(mode="json")


def test_character_schema_requires_canonical_consistency_method() -> None:
    character = {
        "name": "Akira",
        "original_filename": "Akira.png",
        "stored_path": "input/characters/Akira.png",
        "mime_type": "image/png",
        "width": 1024,
        "height": 1536,
        "file_size_bytes": 842120,
        "consistency_method": "ip-adapter-faceid",
        "status": "valid",
        "warnings": [],
    }
    metadata = CharacterMetadata.model_validate({"characters": [character]})
    assert metadata.version == 1

    character["consistency_method"] = "ip_adapter_faceid"
    with pytest.raises(ValidationError):
        CharacterMetadata.model_validate({"characters": [character]})


def test_scene_list_validates_count_unique_ids_and_order() -> None:
    scene_list = SceneList.model_validate(
        {
            "project_id": "akira-episode-1-a7f3c2",
            "story_title": "Akira Episode 1",
            "language": "English",
            "scene_count": 1,
            "scenes": [SCENE],
        }
    )
    assert scene_list.scenes[0].status is SceneStatus.DRAFT

    invalid = scene_list.model_dump(mode="json")
    invalid["scene_count"] = 2
    with pytest.raises(ValidationError):
        SceneList.model_validate(invalid)


@pytest.mark.parametrize(
    "status", ["draft", "approved", "needs_edit", "skipped", "generated", "failed"]
)
def test_scene_status_values(status: str) -> None:
    scene = {**SCENE, "status": status}
    result = SceneList.model_validate(
        {"project_id": "valid-project", "scene_count": 1, "scenes": [scene]}
    )
    assert result.scenes[0].status.value == status


def test_prompt_list_and_status_values() -> None:
    prompt = {
        "scene_id": "scene_001",
        "scene_number": 1,
        "positive_prompt": "anime storyboard illustration",
        "negative_prompt": "text, watermark, logo",
        "characters": [PROMPT_CHARACTER],
        "generation_settings": {"width": 1280, "height": 720},
        "status": "ready",
    }
    prompt_list = PromptList.model_validate(
        {
            "project_id": "valid-project",
            "output_preset": PRESET,
            "prompts": [prompt],
        }
    )

    assert prompt_list.prompts[0].status is PromptStatus.READY
    assert prompt_list.prompts[0].generation_settings.num_inference_steps == 30

    for status in ("ready", "stale", "failed"):
        changed = prompt_list.model_dump(mode="json")
        changed["prompts"][0]["status"] = status
        assert PromptList.model_validate(changed).prompts[0].status.value == status


def test_generation_settings_and_hardware_profile() -> None:
    settings = GenerationSettings.model_validate(
        {
            "project_id": "valid-project",
            "output_preset": PRESET,
            "generation_mode": "auto",
            "image_model": {
                "primary_pipeline": "sdxl",
                "image_model_id": "stabilityai/stable-diffusion-xl-base-1.0",
                "low_vram_image_model_id": "stable-diffusion-v1-5/stable-diffusion-v1-5",
            },
            "defaults": {"negative_prompt": "text, watermark, logo"},
            "hardware": {
                "device": "cuda",
                "gpu_name": "Example GPU",
                "vram_gb": 4.0,
                "cuda_available": True,
                "hardware_profile": "low_vram_4gb",
                "detected_at": NOW,
            },
            "character_consistency": {"enabled": False},
            "updated_at": NOW,
        }
    )

    assert settings.hardware.hardware_profile is HardwareProfile.LOW_VRAM_4GB
    assert settings.defaults.guidance_scale == 7.0


def test_hardware_settings_ignores_legacy_torch_dtype() -> None:
    settings = GenerationSettings.model_validate(
        {
            "project_id": "valid-project",
            "output_preset": PRESET,
            "generation_mode": "auto",
            "image_model": {
                "primary_pipeline": "sdxl",
                "image_model_id": "stabilityai/stable-diffusion-xl-base-1.0",
                "low_vram_image_model_id": "stable-diffusion-v1-5/stable-diffusion-v1-5",
            },
            "defaults": {"negative_prompt": "text, watermark, logo"},
            "hardware": {
                "device": "cuda",
                "gpu_name": "Example GPU",
                "vram_gb": 4.0,
                "cuda_available": True,
                "torch_dtype": "float16",
                "hardware_profile": "low_vram_4gb",
                "detected_at": NOW,
            },
            "character_consistency": {"enabled": False},
            "updated_at": NOW,
        }
    )

    assert "torch_dtype" not in settings.hardware.model_dump(mode="json")


def test_generation_job_schema() -> None:
    job = GenerationJob.model_validate(
        {
            "project_id": "valid-project",
            "job_id": "gen_20260611_101530",
            "status": "running",
            "started_at": NOW,
            "updated_at": NOW,
            "generation_plan": {
                "pipeline": "sd15",
                "model_id": "stable-diffusion-v1-5",
                "device": "cuda",
                "torch_dtype": "float16",
                "output_preset_id": "low_vram_preview",
            },
            "character_consistency": {
                "method": "ip-adapter-faceid",
                "mode": "faceid_disabled_low_vram",
                "enabled": False,
            },
            "total_scenes": 1,
        }
    )

    assert job.version == 1
    assert job.status.value == "running"


def test_output_manifest_success_and_failure_rules() -> None:
    asset = {
        "asset_id": "asset_scene_001_job",
        "job_id": "job",
        "scene_id": "scene_001",
        "scene_number": 1,
        "scene_title": "Akira enters",
        "prompt_id": "scene_001",
        "output_filename": "001_akira_enters.png",
        "output_path": "outputs/images/001_akira_enters.png",
        "width": 1280,
        "height": 720,
        "status": "success",
        "image_model_id": "model",
        "pipeline": "sdxl",
        "seed": 42,
        "output_preset_id": "youtube_standard",
        "character_references": [
            {
                "name": "Akira",
                "reference_image_path": "input/characters/Akira.png",
                "consistency_method": "ip-adapter-faceid",
                "runtime_consistency_mode": "faceid_enabled",
            }
        ],
        "created_at": NOW,
    }
    manifest_data = {
        "project_id": "valid-project",
        "latest_job_id": "job",
        "created_at": NOW,
        "updated_at": NOW,
        "assets": [asset],
    }
    manifest = OutputManifest.model_validate(manifest_data)
    assert manifest.assets[0].output_path.startswith("outputs/")

    failed = deepcopy(manifest_data)
    failed["assets"][0].update(
        {
            "status": "failed",
            "output_filename": None,
            "output_path": None,
            "error_code": "CUDA_OUT_OF_MEMORY",
        }
    )
    assert OutputManifest.model_validate(failed).assets[0].status.value == "failed"

    failed["assets"][0]["error_code"] = None
    with pytest.raises(ValidationError):
        OutputManifest.model_validate(failed)
