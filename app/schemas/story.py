from datetime import datetime
from enum import Enum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class StoryStatus(str, Enum):
    UPLOADED = "UPLOADED"
    INVALID = "INVALID"


class StoryMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    version: int = Field(default=1, ge=1)
    story_status: StoryStatus
    original_filename: str = Field(min_length=1)
    stored_path: str = Field(min_length=1)
    file_size_bytes: int = Field(ge=1, le=1024 * 1024)
    story_char_count: int = Field(
        ge=1,
        le=120_000,
        validation_alias=AliasChoices("story_char_count", "character_count"),
    )
    approx_word_count: int = Field(ge=1)
    line_count: int = Field(ge=1)
    encoding: str = Field(default="utf-8", pattern=r"^utf-8$")
    uploaded_at: datetime
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    normalized_line_endings: bool = True
