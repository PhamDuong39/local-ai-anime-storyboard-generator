from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ConsistencyMethod = Literal["ip-adapter-faceid"]


class CharacterStatus(str, Enum):
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"
    MISSING = "missing"


class CharacterReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    original_filename: str = Field(min_length=1)
    stored_path: str = Field(min_length=1)
    mime_type: str = Field(pattern=r"^image/(png|jpeg|webp)$")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    file_size_bytes: int = Field(gt=0)
    is_full_body_expected: bool = True
    consistency_method: ConsistencyMethod = "ip-adapter-faceid"
    status: CharacterStatus
    warnings: list[str] = Field(default_factory=list)


class CharacterMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    characters: list[CharacterReference] = Field(default_factory=list)
