from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SceneStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    NEEDS_EDIT = "needs_edit"
    SKIPPED = "skipped"
    GENERATED = "generated"
    FAILED = "failed"


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(pattern=r"^scene_\d{3,}$")
    scene_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=80)
    source_excerpt: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    characters: list[str] = Field(default_factory=list)
    location: str = Field(min_length=1)
    time_of_day: str = Field(min_length=1)
    mood: str = Field(min_length=1)
    main_action: str = Field(min_length=1)
    camera_shot: str = Field(min_length=1)
    camera_angle: str = Field(min_length=1)
    visual_details: list[str] = Field(min_length=3, max_length=8)
    continuity_notes: list[str] = Field(default_factory=list)
    status: SceneStatus = SceneStatus.DRAFT


class SceneList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    project_id: str = Field(min_length=1)
    story_title: str | None = None
    language: str = "unknown"
    scene_count: int = Field(ge=0)
    scenes: list[Scene]

    @property
    def active_scenes(self) -> list[Scene]:
        """Scenes eligible for approval, prompting, and image generation."""
        return [scene for scene in self.scenes if scene.status is not SceneStatus.SKIPPED]

    @model_validator(mode="after")
    def validate_scene_order(self) -> "SceneList":
        if self.scene_count != len(self.scenes):
            raise ValueError("scene_count must match the number of scenes")
        if len({scene.scene_id for scene in self.scenes}) != len(self.scenes):
            raise ValueError("scene IDs must be unique")
        if [scene.scene_number for scene in self.active_scenes] != list(
            range(1, len(self.active_scenes) + 1)
        ):
            raise ValueError("active scene numbers must be sequential and 1-based")
        return self
