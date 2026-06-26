from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.character import ConsistencyMethod
from app.schemas.project import OutputPreset


class GenerationMode(str, Enum):
    AUTO = "auto"
    QUALITY = "quality"
    LOW_VRAM = "low_vram"
    CPU = "cpu"


class HardwareProfile(str, Enum):
    CPU_ONLY = "cpu_only"
    LOW_VRAM_4GB = "low_vram_4gb"
    MID_VRAM_6_8GB = "mid_vram_6_8gb"
    HIGH_VRAM_12GB_PLUS = "high_vram_12gb_plus"
    UNKNOWN = "unknown"


class PipelineKind(str, Enum):
    SDXL = "sdxl"
    SD15 = "sd15"


class ImageModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_pipeline: PipelineKind = PipelineKind.SDXL
    image_model_id: str = Field(min_length=1)
    low_vram_image_model_id: str = Field(min_length=1)


class GenerationDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    num_images_per_scene: int = Field(default=1, ge=1)
    num_inference_steps: int = Field(default=30, ge=1)
    guidance_scale: float = Field(default=7.0, gt=0)
    seed_policy: Literal[
        "random_per_scene", "fixed_project_seed", "manual_per_scene"
    ] = "random_per_scene"
    scheduler: str = "default"
    negative_prompt: str = Field(min_length=1)


class HardwareSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: str = Field(min_length=1)
    gpu_name: str | None = None
    vram_gb: float = Field(ge=0)
    cuda_available: bool
    hardware_profile: HardwareProfile
    detected_at: datetime

    @model_validator(mode="before")
    @classmethod
    def drop_legacy_torch_dtype(cls, value: object) -> object:
        if isinstance(value, dict) and "torch_dtype" in value:
            cleaned = dict(value)
            cleaned.pop("torch_dtype")
            return cleaned
        return value


class HardwareDetection(HardwareSettings):
    """First-pass hardware detection output.

    Runtime dtype choices belong to GenerationPlan, not hardware metadata.
    """


class CharacterConsistencySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: ConsistencyMethod = "ip-adapter-faceid"
    enable_mode: Literal["auto", "force", "disabled"] = "auto"
    enabled: bool
    disabled_reason: str = ""
    fallback: Literal["prompt_based_character_hints"] = "prompt_based_character_hints"


class GenerationSafetySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force_low_vram_mode: bool = False
    continue_on_scene_failure: bool = True
    overwrite_existing_outputs: bool = False


class GenerationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    project_id: str = Field(min_length=1)
    output_preset: OutputPreset
    generation_mode: GenerationMode = GenerationMode.AUTO
    image_model: ImageModelSettings
    defaults: GenerationDefaults
    hardware: HardwareSettings
    character_consistency: CharacterConsistencySettings
    safety: GenerationSafetySettings = Field(default_factory=GenerationSafetySettings)
    updated_at: datetime


class GenerationReadinessIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, object] = Field(default_factory=dict)


class GenerationReadinessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    project_id: str = Field(min_length=1)
    active_scene_count: int = Field(default=0, ge=0)
    prompt_count: int = Field(default=0, ge=0)
    hardware: HardwareDetection | None = None
    warnings: list[GenerationReadinessIssue] = Field(default_factory=list)
    blocking_errors: list[GenerationReadinessIssue] = Field(default_factory=list)
