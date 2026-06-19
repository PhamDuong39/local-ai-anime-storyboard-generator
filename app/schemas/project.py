from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    STORY_UPLOADED = "STORY_UPLOADED"
    CHARACTERS_UPLOADED = "CHARACTERS_UPLOADED"
    SCENES_GENERATED = "SCENES_GENERATED"
    SCENES_APPROVED = "SCENES_APPROVED"
    PROMPTS_GENERATED = "PROMPTS_GENERATED"
    GENERATION_RUNNING = "GENERATION_RUNNING"
    GENERATION_COMPLETED = "GENERATION_COMPLETED"
    STORY_UPLOAD_FAILED = "STORY_UPLOAD_FAILED"
    CHARACTER_VALIDATION_FAILED = "CHARACTER_VALIDATION_FAILED"
    SCENE_SPLITTING_FAILED = "SCENE_SPLITTING_FAILED"
    PROMPT_GENERATION_FAILED = "PROMPT_GENERATION_FAILED"
    GENERATION_FAILED = "GENERATION_FAILED"
    GENERATION_PARTIAL = "GENERATION_PARTIAL"


class OutputPresetId(str, Enum):
    YOUTUBE_STANDARD = "youtube_standard"
    YOUTUBE_HIGH = "youtube_high"
    LOW_VRAM_PREVIEW = "low_vram_preview"
    LOW_VRAM_TINY = "low_vram_tiny"
    SQUARE_PREVIEW = "square_preview"
    VERTICAL_SHORT = "vertical_short"


class OutputPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: OutputPresetId
    name: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    aspect_ratio: str = Field(pattern=r"^\d+:\d+$")


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    project_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,80}$")
    project_name: str = Field(min_length=1)
    description: str = ""
    status: ProjectStatus = ProjectStatus.CREATED
    output_preset: OutputPreset
    created_at: datetime
    updated_at: datetime
