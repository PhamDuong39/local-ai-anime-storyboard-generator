from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    gpu_name: str = ""
    vram_gb: float = Field(ge=0)
    cuda_available: bool
    torch_dtype: str = Field(min_length=1)
    hardware_profile: HardwareProfile
    detected_at: datetime


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
