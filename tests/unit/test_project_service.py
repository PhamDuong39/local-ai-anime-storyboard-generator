import re

import pytest

from app.core.errors import AppError
from app.core.file_io import read_json
from app.schemas.generation import GenerationSettings
from app.schemas.project import ProjectMetadata, ProjectStatus
from app.services.project_service import ProjectService, workflow_for_status


def make_service(tmp_path):
    return ProjectService(
        tmp_path / "projects",
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    )


def test_generate_project_id_uses_safe_slug_and_suffix(tmp_path) -> None:
    project_id = make_service(tmp_path).generate_project_id("Akira: Episode 1")

    assert re.fullmatch(r"akira-episode-1-[a-f0-9]{6}", project_id)


def test_generate_project_id_rejects_blank_name(tmp_path) -> None:
    with pytest.raises(AppError, match="Enter a project name"):
        make_service(tmp_path).generate_project_id("  ")


def test_create_project_builds_folders_and_valid_metadata(tmp_path) -> None:
    service = make_service(tmp_path)
    project = service.create_project(
        "Akira Episode 1", "youtube_standard", "Opening episode"
    )
    root = tmp_path / "projects" / project.project_id

    for relative_path in (
        "input/characters",
        "metadata/character_cache",
        "outputs/images",
        "logs",
    ):
        assert (root / relative_path).is_dir()

    stored_project = ProjectMetadata.model_validate(
        read_json(root / "metadata/project.json")
    )
    settings = GenerationSettings.model_validate(
        read_json(root / "metadata/generation_settings.json")
    )
    assert stored_project.status.value == "CREATED"
    assert stored_project.output_preset.id.value == "youtube_standard"
    assert settings.project_id == project.project_id
    assert settings.character_consistency.method == "ip-adapter-faceid"
    assert settings.hardware.hardware_profile.value == "unknown"


def test_create_project_rejects_unknown_preset(tmp_path) -> None:
    with pytest.raises(AppError, match="available output presets"):
        make_service(tmp_path).create_project("Akira", "legacy_preset")


@pytest.mark.parametrize(
    ("status", "current_step", "path_suffix"),
    [
        (ProjectStatus.CREATED, "story", "story"),
        (ProjectStatus.STORY_UPLOAD_FAILED, "story", "story"),
        (ProjectStatus.STORY_UPLOADED, "characters", "characters"),
        (ProjectStatus.CHARACTER_VALIDATION_FAILED, "characters", "characters"),
        (ProjectStatus.CHARACTERS_UPLOADED, "scenes", "scenes"),
        (ProjectStatus.SCENE_SPLITTING_FAILED, "scenes", "scenes"),
        (ProjectStatus.SCENES_GENERATED, "scenes", "scenes"),
        (ProjectStatus.SCENES_APPROVED, "prompts", "prompts"),
        (ProjectStatus.PROMPT_GENERATION_FAILED, "prompts", "prompts"),
        (ProjectStatus.PROMPTS_GENERATED, "generation", "generation"),
        (ProjectStatus.GENERATION_RUNNING, "generation", "generation"),
        (ProjectStatus.GENERATION_FAILED, "generation", "generation"),
        (ProjectStatus.GENERATION_PARTIAL, "outputs", "outputs"),
        (ProjectStatus.GENERATION_COMPLETED, "outputs", "outputs"),
    ],
)
def test_workflow_for_status_maps_every_project_state(
    status: ProjectStatus, current_step: str, path_suffix: str
) -> None:
    workflow = workflow_for_status(status)

    assert workflow.current_step == current_step
    assert workflow.next_url("akira-123abc") == (
        f"/projects/akira-123abc/{path_suffix}"
    )
