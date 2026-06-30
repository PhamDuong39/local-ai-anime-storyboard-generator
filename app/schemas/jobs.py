from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.generation import PipelineKind
from app.schemas.manifest import RuntimeConsistencyMode
from app.schemas.project import OutputPresetId


class GenerationJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class GenerationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineKind
    model_id: str = Field(min_length=1)
    device: str = Field(min_length=1)
    torch_dtype: str = Field(min_length=1)
    output_preset_id: OutputPresetId


class JobCharacterConsistency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = Field(pattern=r"^ip-adapter-faceid$")
    mode: RuntimeConsistencyMode
    enabled: bool
    disabled_reason: str = ""
    fallback: str = "prompt_based_character_hints"


class SceneResultStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SceneGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(pattern=r"^scene_\d{3,}$")
    scene_number: int = Field(ge=1)
    status: SceneResultStatus
    output_path: str | None = None
    seed: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class GenerationJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    project_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    status: GenerationJobStatus
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    generation_plan: GenerationPlan
    character_consistency: JobCharacterConsistency
    total_scenes: int = Field(ge=0)
    completed_scenes: int = Field(default=0, ge=0)
    failed_scenes: int = Field(default=0, ge=0)
    skipped_scenes: int = Field(default=0, ge=0)
    current_scene_id: str | None = None
    current_scene_number: int | None = Field(default=None, ge=1)
    current_scene_title: str | None = None
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_message: str = ""
    scene_results: list[SceneGenerationResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
