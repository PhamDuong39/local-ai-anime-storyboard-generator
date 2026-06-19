from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.character import ConsistencyMethod
from app.schemas.project import OutputPreset


class PromptStatus(str, Enum):
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"


class PromptCharacter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    reference_image_path: str = Field(min_length=1)
    consistency_method: ConsistencyMethod = "ip-adapter-faceid"
    role_in_scene: str = Field(min_length=1)
    visual_priority: str = Field(min_length=1)


class PromptGenerationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    num_images: int = Field(default=1, ge=1)
    seed: int | None = Field(default=None, ge=0)
    guidance_scale: float = Field(default=7.0, gt=0)
    num_inference_steps: int = Field(default=30, ge=1)


class Prompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(pattern=r"^scene_\d{3,}$")
    scene_number: int = Field(ge=1)
    positive_prompt: str = Field(min_length=1)
    negative_prompt: str = Field(min_length=1)
    characters: list[PromptCharacter] = Field(default_factory=list)
    generation_settings: PromptGenerationSettings
    status: PromptStatus
    manual_edit: bool = False


class PromptList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    project_id: str = Field(min_length=1)
    prompt_version: int = Field(default=1, ge=1)
    style_preset: str = "anime_storyboard_default"
    output_preset: OutputPreset
    prompts: list[Prompt]

    @model_validator(mode="after")
    def validate_prompt_mapping(self) -> "PromptList":
        scene_ids = [prompt.scene_id for prompt in self.prompts]
        if len(set(scene_ids)) != len(scene_ids):
            raise ValueError("each scene must map to exactly one prompt")
        return self
