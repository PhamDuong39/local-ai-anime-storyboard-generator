from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.character import ConsistencyMethod
from app.schemas.generation import PipelineKind
from app.schemas.project import OutputPresetId


class OutputAssetStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class RuntimeConsistencyMode(str, Enum):
    FACEID_ENABLED = "faceid_enabled"
    FACEID_DISABLED_LOW_VRAM = "faceid_disabled_low_vram"
    FACEID_UNAVAILABLE = "faceid_unavailable"
    PROMPT_ONLY = "prompt_only"


class OutputCharacterReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    reference_image_path: str = Field(min_length=1)
    consistency_method: ConsistencyMethod = "ip-adapter-faceid"
    runtime_consistency_mode: RuntimeConsistencyMode


class OutputAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    scene_id: str = Field(pattern=r"^scene_\d{3,}$")
    scene_number: int = Field(ge=1)
    scene_title: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    output_filename: str | None = None
    output_path: str | None = None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    status: OutputAssetStatus
    image_model_id: str = Field(min_length=1)
    pipeline: PipelineKind
    seed: int = Field(ge=0)
    num_inference_steps: int = Field(default=30, ge=1)
    guidance_scale: float = Field(default=7.0, gt=0)
    output_preset_id: OutputPresetId
    character_references: list[OutputCharacterReference] = Field(default_factory=list)
    positive_prompt_hash: str | None = None
    negative_prompt_hash: str | None = None
    created_at: datetime
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_result_fields(self) -> "OutputAsset":
        if self.status is OutputAssetStatus.SUCCESS and (
            not self.output_filename or not self.output_path
        ):
            raise ValueError("successful assets require output filename and path")
        if self.status is OutputAssetStatus.FAILED and not self.error_code:
            raise ValueError("failed assets require an error code")
        return self


class OutputManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    project_id: str = Field(min_length=1)
    latest_job_id: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    assets: list[OutputAsset] = Field(default_factory=list)
