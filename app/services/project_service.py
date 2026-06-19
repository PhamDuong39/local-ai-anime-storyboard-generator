import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from app.core.errors import AppError
from app.core.file_io import read_json_model, write_json
from app.core.paths import metadata_path, project_root, validate_project_id
from app.schemas.generation import (
    CharacterConsistencySettings,
    GenerationDefaults,
    GenerationSafetySettings,
    GenerationSettings,
    HardwareProfile,
    HardwareSettings,
    ImageModelSettings,
)
from app.schemas.project import OutputPreset, OutputPresetId, ProjectMetadata


DEFAULT_NEGATIVE_PROMPT = (
    "low quality, blurry, pixelated, distorted face, asymmetrical eyes, bad anatomy, "
    "bad hands, extra fingers, missing fingers, duplicate character, inconsistent "
    "outfit, inconsistent hairstyle, text, subtitle, speech bubble, watermark, logo, "
    "cropped face, cropped body"
)

OUTPUT_PRESETS: dict[OutputPresetId, OutputPreset] = {
    OutputPresetId.YOUTUBE_STANDARD: OutputPreset(
        id=OutputPresetId.YOUTUBE_STANDARD,
        name="YouTube Standard",
        width=1280,
        height=720,
        aspect_ratio="16:9",
    ),
    OutputPresetId.YOUTUBE_HIGH: OutputPreset(
        id=OutputPresetId.YOUTUBE_HIGH,
        name="YouTube High",
        width=1920,
        height=1080,
        aspect_ratio="16:9",
    ),
    OutputPresetId.LOW_VRAM_PREVIEW: OutputPreset(
        id=OutputPresetId.LOW_VRAM_PREVIEW,
        name="Low VRAM Preview",
        width=960,
        height=540,
        aspect_ratio="16:9",
    ),
    OutputPresetId.LOW_VRAM_TINY: OutputPreset(
        id=OutputPresetId.LOW_VRAM_TINY,
        name="Low VRAM Tiny",
        width=768,
        height=432,
        aspect_ratio="16:9",
    ),
    OutputPresetId.SQUARE_PREVIEW: OutputPreset(
        id=OutputPresetId.SQUARE_PREVIEW,
        name="Square Preview",
        width=1024,
        height=1024,
        aspect_ratio="1:1",
    ),
    OutputPresetId.VERTICAL_SHORT: OutputPreset(
        id=OutputPresetId.VERTICAL_SHORT,
        name="Vertical Short",
        width=1080,
        height=1920,
        aspect_ratio="9:16",
    ),
}


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_value)).strip("-")


class ProjectService:
    def __init__(
        self,
        projects_root: str | Path,
        *,
        image_model_id: str,
        low_vram_image_model_id: str,
        enable_ip_adapter_faceid: Literal["auto", "force", "disabled"] = "auto",
        force_low_vram_mode: bool = False,
    ) -> None:
        self.projects_root = Path(projects_root)
        self.image_model_id = image_model_id
        self.low_vram_image_model_id = low_vram_image_model_id
        self.enable_ip_adapter_faceid = enable_ip_adapter_faceid
        self.force_low_vram_mode = force_low_vram_mode

    def generate_project_id(self, project_name: str) -> str:
        name = project_name.strip()
        if not name:
            raise AppError(
                code="PROJECT_NAME_REQUIRED",
                message="Enter a project name to continue.",
                http_status=422,
            )

        slug = _slugify(name)[:74].strip("-")
        if not slug:
            slug = "project"
        project_id = f"{slug}-{uuid4().hex[:6]}"
        return validate_project_id(project_id)

    def create_project(
        self,
        project_name: str,
        output_preset_id: str,
        description: str = "",
    ) -> ProjectMetadata:
        try:
            preset_id = OutputPresetId(output_preset_id)
        except ValueError as exc:
            raise AppError(
                code="OUTPUT_PRESET_INVALID",
                message="Choose one of the available output presets.",
                http_status=422,
            ) from exc

        project_id = self.generate_project_id(project_name)
        root = project_root(self.projects_root, project_id)
        now = datetime.now(timezone.utc)
        preset = OUTPUT_PRESETS[preset_id]
        project = ProjectMetadata(
            project_id=project_id,
            project_name=project_name.strip(),
            description=description.strip(),
            output_preset=preset,
            created_at=now,
            updated_at=now,
        )
        settings = GenerationSettings(
            project_id=project_id,
            output_preset=preset,
            image_model=ImageModelSettings(
                image_model_id=self.image_model_id,
                low_vram_image_model_id=self.low_vram_image_model_id,
            ),
            defaults=GenerationDefaults(negative_prompt=DEFAULT_NEGATIVE_PROMPT),
            hardware=HardwareSettings(
                device="unknown",
                vram_gb=0,
                cuda_available=False,
                torch_dtype="unknown",
                hardware_profile=HardwareProfile.UNKNOWN,
                detected_at=now,
            ),
            character_consistency=CharacterConsistencySettings(
                enable_mode=self.enable_ip_adapter_faceid,
                enabled=False,
                disabled_reason="hardware_not_detected",
            ),
            safety=GenerationSafetySettings(
                force_low_vram_mode=self.force_low_vram_mode
            ),
            updated_at=now,
        )

        try:
            root.mkdir(parents=True, exist_ok=False)
            for relative_dir in (
                "input/characters",
                "metadata/character_cache",
                "outputs/images",
                "logs",
            ):
                (root / relative_dir).mkdir(parents=True)
            write_json(
                metadata_path(self.projects_root, project_id, "project.json"), project
            )
            write_json(
                metadata_path(
                    self.projects_root, project_id, "generation_settings.json"
                ),
                settings,
            )
        except FileExistsError as exc:
            raise AppError(
                code="PROJECT_ID_CONFLICT",
                message="Could not create a unique project. Please try again.",
                http_status=409,
            ) from exc
        except Exception:
            if root.exists():
                shutil.rmtree(root)
            raise

        return project

    def get_project(self, project_id: str) -> ProjectMetadata:
        try:
            path = metadata_path(self.projects_root, project_id, "project.json")
        except ValueError as exc:
            raise AppError(
                code="PROJECT_NOT_FOUND",
                message="This project could not be found.",
                http_status=404,
            ) from exc

        if not path.is_file():
            raise AppError(
                code="PROJECT_NOT_FOUND",
                message="This project could not be found.",
                http_status=404,
            )
        return read_json_model(path, ProjectMetadata)
