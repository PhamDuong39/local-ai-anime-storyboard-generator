from datetime import datetime, timezone

from app.core.file_io import read_json_model, write_json
from app.core.paths import metadata_path, project_root
from app.schemas.character import CharacterMetadata
from app.schemas.generation import HardwareDetection, HardwareProfile
from app.schemas.jobs import GenerationJobStatus, SceneResultStatus
from app.schemas.project import ProjectMetadata, ProjectStatus
from app.schemas.prompt import PromptList
from app.schemas.scene import SceneList
from app.services.generation_job_service import GenerationJobService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.scene_service import SceneService


NOW = datetime(2026, 6, 11, 10, 15, 30, tzinfo=timezone.utc)


class FakeHardwareService:
    def __init__(self, profile: HardwareProfile = HardwareProfile.HIGH_VRAM_12GB_PLUS):
        self.profile = profile

    def detect_hardware(self) -> HardwareDetection:
        if self.profile is HardwareProfile.CPU_ONLY:
            return HardwareDetection(
                device="cpu",
                gpu_name=None,
                vram_gb=0,
                cuda_available=False,
                hardware_profile=self.profile,
                detected_at=NOW,
            )
        if self.profile is HardwareProfile.LOW_VRAM_4GB:
            return HardwareDetection(
                device="cuda",
                gpu_name="Low VRAM GPU",
                vram_gb=4,
                cuda_available=True,
                hardware_profile=self.profile,
                detected_at=NOW,
            )
        return HardwareDetection(
            device="cuda",
            gpu_name="High VRAM GPU",
            vram_gb=12,
            cuda_available=True,
            hardware_profile=self.profile,
            detected_at=NOW,
        )


def scene(status: str = "approved") -> dict[str, object]:
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


def prompt(status: str = "ready") -> dict[str, object]:
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
        "status": status,
    }


def make_project(tmp_path) -> tuple[object, str, str]:
    root = tmp_path / "projects"
    project = ProjectService(
        root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("Generation Readiness", "youtube_standard")
    return root, project.project_id, project.output_preset.model_dump(mode="json")


def save_scenes(root, project_id: str, status: str = "approved") -> None:
    SceneService(root).save_scenes(
        project_id,
        SceneList.model_validate(
            {
                "project_id": project_id,
                "scene_count": 1,
                "scenes": [scene(status)],
            }
        ),
    )


def save_prompts(root, project_id: str, preset: dict[str, object], status: str = "ready"):
    PromptService(root).save_prompts(
        project_id,
        PromptList.model_validate(
            {
                "project_id": project_id,
                "output_preset": preset,
                "prompts": [prompt(status)],
            }
        ),
    )


def save_character(root, project_id: str) -> None:
    character_path = project_root(root, project_id) / "input/characters/Akira.png"
    character_path.write_bytes(b"reference")
    write_json(
        metadata_path(root, project_id, "characters.json"),
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


def make_ready_project(tmp_path) -> tuple[GenerationJobService, str]:
    root, project_id, preset = make_project(tmp_path)
    save_scenes(root, project_id)
    save_character(root, project_id)
    save_prompts(root, project_id, preset)
    return (
        GenerationJobService(root, hardware_service=FakeHardwareService()),
        project_id,
    )


def codes(result) -> list[str]:
    return [error.code for error in result.blocking_errors]


def test_missing_project_blocks_generation(tmp_path) -> None:
    result = GenerationJobService(
        tmp_path / "projects", hardware_service=FakeHardwareService()
    ).check_readiness("missing-project")

    assert result.ok is False
    assert codes(result) == ["PROJECT_NOT_FOUND"]


def test_running_job_blocks_generation(tmp_path) -> None:
    _, project_id = make_ready_project(tmp_path)
    result = GenerationJobService(
        tmp_path / "projects",
        hardware_service=FakeHardwareService(),
        is_job_running=lambda: True,
    ).check_readiness(project_id)

    assert "GENERATION_ALREADY_RUNNING" in codes(result)


def test_missing_scenes_block_generation(tmp_path) -> None:
    root, project_id, _ = make_project(tmp_path)
    result = GenerationJobService(
        root, hardware_service=FakeHardwareService()
    ).check_readiness(project_id)

    assert "SCENE_LIST_NOT_FOUND" in codes(result)


def test_unapproved_scenes_block_generation(tmp_path) -> None:
    root, project_id, _ = make_project(tmp_path)
    save_scenes(root, project_id, "draft")
    result = GenerationJobService(
        root, hardware_service=FakeHardwareService()
    ).check_readiness(project_id)

    assert "SCENE_APPROVAL_REQUIRED" in codes(result)


def test_missing_prompts_block_generation(tmp_path) -> None:
    root, project_id, _ = make_project(tmp_path)
    save_scenes(root, project_id)
    save_character(root, project_id)
    result = GenerationJobService(
        root, hardware_service=FakeHardwareService()
    ).check_readiness(project_id)

    assert "PROMPTS_MISSING" in codes(result)


def test_stale_prompt_blocks_generation(tmp_path) -> None:
    root, project_id, preset = make_project(tmp_path)
    save_scenes(root, project_id)
    save_character(root, project_id)
    save_prompts(root, project_id, preset, "stale")
    result = GenerationJobService(
        root, hardware_service=FakeHardwareService()
    ).check_readiness(project_id)

    assert "PROMPT_STALE" in codes(result)


def test_missing_character_reference_blocks_generation(tmp_path) -> None:
    root, project_id, preset = make_project(tmp_path)
    save_scenes(root, project_id)
    save_prompts(root, project_id, preset)
    result = GenerationJobService(
        root, hardware_service=FakeHardwareService()
    ).check_readiness(project_id)

    assert "CHARACTER_REFERENCE_MISSING" in codes(result)


def test_unwritable_output_folder_blocks_generation(tmp_path) -> None:
    service, project_id = make_ready_project(tmp_path)
    service = GenerationJobService(
        tmp_path / "projects",
        hardware_service=FakeHardwareService(),
        output_writable_checker=lambda _: False,
    )

    result = service.check_readiness(project_id)

    assert "OUTPUT_FOLDER_NOT_WRITABLE" in codes(result)


def test_invalid_model_config_blocks_generation(tmp_path) -> None:
    root, project_id, preset = make_project(tmp_path)
    save_scenes(root, project_id)
    save_character(root, project_id)
    save_prompts(root, project_id, preset)
    write_json(metadata_path(root, project_id, "generation_settings.json"), {"bad": True})
    result = GenerationJobService(
        root, hardware_service=FakeHardwareService()
    ).check_readiness(project_id)

    assert "MODEL_CONFIG_INVALID" in codes(result)


def test_cpu_generation_requires_confirmation(tmp_path) -> None:
    root, project_id, preset = make_project(tmp_path)
    save_scenes(root, project_id)
    save_character(root, project_id)
    save_prompts(root, project_id, preset)
    service = GenerationJobService(
        root,
        hardware_service=FakeHardwareService(HardwareProfile.CPU_ONLY),
    )

    blocked = service.check_readiness(project_id)
    confirmed = service.check_readiness(project_id, confirm_cpu_slow=True)

    assert "CPU_GENERATION_CONFIRMATION_REQUIRED" in codes(blocked)
    assert confirmed.ok is True
    assert [warning.code for warning in confirmed.warnings] == ["CPU_GENERATION_SLOW"]


def test_low_vram_warning_is_surfaced_without_blocking(tmp_path) -> None:
    root, project_id, preset = make_project(tmp_path)
    save_scenes(root, project_id)
    save_character(root, project_id)
    save_prompts(root, project_id, preset)
    result = GenerationJobService(
        root,
        hardware_service=FakeHardwareService(HardwareProfile.LOW_VRAM_4GB),
    ).check_readiness(project_id)

    assert result.ok is True
    assert [warning.code for warning in result.warnings] == [
        "LOW_VRAM_MODE_RECOMMENDED"
    ]


def test_start_job_raises_first_blocking_error(tmp_path) -> None:
    root, project_id, _ = make_project(tmp_path)

    try:
        GenerationJobService(
            root, hardware_service=FakeHardwareService()
        ).start_job(project_id)
    except Exception as exc:
        assert getattr(exc, "code") == "SCENE_LIST_NOT_FOUND"
    else:
        raise AssertionError("start_job should have blocked missing scenes")


def test_ready_project_can_start_generation_gate(tmp_path) -> None:
    service, project_id = make_ready_project(tmp_path)
    project = read_json_model(
        metadata_path(tmp_path / "projects", project_id, "project.json"),
        ProjectMetadata,
    )
    project.status = ProjectStatus.PROMPTS_GENERATED
    write_json(metadata_path(tmp_path / "projects", project_id, "project.json"), project)

    job = service.start_job(project_id)

    assert job.status is GenerationJobStatus.QUEUED
    assert job.total_scenes == 1
    assert job.progress_percent == 0


def test_starting_job_creates_generation_status_json(tmp_path) -> None:
    service, project_id = make_ready_project(tmp_path)

    job = service.start_job(project_id)

    stored = service.get_status(project_id)
    assert stored == job
    assert (
        metadata_path(tmp_path / "projects", project_id, "generation_status.json")
    ).is_file()
    assert stored is not None
    assert stored.generation_plan.model_id == "sdxl-model"
    assert stored.character_consistency.method == "ip-adapter-faceid"


def test_active_generation_status_blocks_second_job(tmp_path) -> None:
    service, project_id = make_ready_project(tmp_path)
    service.start_job(project_id)

    result = service.check_readiness(project_id)

    assert "GENERATION_ALREADY_RUNNING" in codes(result)


def test_scene_progress_update_is_persisted(tmp_path) -> None:
    service, project_id = make_ready_project(tmp_path)
    service.start_job(project_id)
    service.mark_running(
        project_id,
        scene_id="scene_001",
        scene_number=1,
        scene_title="School gate",
    )

    updated = service.record_scene_result(
        project_id,
        scene_id="scene_001",
        scene_number=1,
        status=SceneResultStatus.SUCCESS,
        output_path="outputs/images/001_school_gate.png",
    )
    stored = service.get_status(project_id)

    assert stored == updated
    assert stored is not None
    assert stored.status is GenerationJobStatus.RUNNING
    assert stored.completed_scenes == 1
    assert stored.failed_scenes == 0
    assert stored.progress_percent == 100
    assert stored.scene_results[0].scene_id == "scene_001"
    assert stored.scene_results[0].status is SceneResultStatus.SUCCESS
