from datetime import datetime, timezone

from PIL import Image

from app.core.file_io import read_json, write_json
from app.core.paths import metadata_path, project_root
from app.schemas.character import CharacterMetadata
from app.schemas.generation import HardwareDetection, HardwareProfile
from app.schemas.prompt import PromptList
from app.schemas.project import ProjectStatus
from app.schemas.scene import SceneList
from app.services.generation_job_service import GenerationJobService
from app.services.generation_service import GenerationService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.scene_service import SceneService


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


def scene() -> dict[str, object]:
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
        "status": "approved",
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


def make_ready_project(tmp_path):
    root = tmp_path / "projects"
    project = ProjectService(
        root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("Mock Generation", "youtube_standard")
    SceneService(root).save_scenes(
        project.project_id,
        SceneList.model_validate(
            {
                "project_id": project.project_id,
                "scene_count": 1,
                "scenes": [scene()],
            }
        ),
    )
    character_path = (
        project_root(root, project.project_id) / "input/characters/Akira.png"
    )
    character_path.write_bytes(b"reference")
    write_json(
        metadata_path(root, project.project_id, "characters.json"),
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
    PromptService(root).save_prompts(
        project.project_id,
        PromptList.model_validate(
            {
                "project_id": project.project_id,
                "output_preset": project.output_preset.model_dump(mode="json"),
                "prompts": [prompt()],
            }
        ),
    )
    return root, project


def test_mock_generation_writes_png_manifest_status_and_project_state(tmp_path) -> None:
    root, project = make_ready_project(tmp_path)
    job_service = GenerationJobService(root, hardware_service=FakeHardwareService())
    job = job_service.start_job(project.project_id)

    GenerationService(root).generate_mock_images(project.project_id, job.job_id)

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    project_metadata = read_json(root / project.project_id / "metadata/project.json")
    image_path = root / project.project_id / manifest["assets"][0]["output_path"]

    assert status["status"] == "completed"
    assert status["completed_scenes"] == 1
    assert manifest["assets"][0]["scene_id"] == "scene_001"
    assert manifest["assets"][0]["output_filename"] == "001_school_gate.png"
    assert project_metadata["status"] == ProjectStatus.GENERATION_COMPLETED.value
    assert Image.open(image_path).size == (1280, 720)
