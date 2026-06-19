import hashlib
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.core.file_io import read_json, sha256_file, sha256_text, write_json


class ExampleMetadata(BaseModel):
    version: str = "1.0"
    name: str


def test_write_read_roundtrip_creates_parent_folders(tmp_path: Path) -> None:
    path = tmp_path / "metadata" / "project.json"

    write_json(path, {"version": "1.0", "title": "Akira"})

    assert read_json(path) == {"version": "1.0", "title": "Akira"}
    assert not list(path.parent.glob("*.tmp"))


def test_write_json_replaces_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "project.json"
    write_json(path, {"status": "created"})

    write_json(path, {"status": "story_uploaded"})

    assert read_json(path) == {"status": "story_uploaded"}


def test_write_json_supports_pydantic_models(tmp_path: Path) -> None:
    path = tmp_path / "metadata.json"

    write_json(path, ExampleMetadata(name="Hana"))

    assert read_json(path) == {"version": "1.0", "name": "Hana"}


def test_serialization_failure_preserves_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "project.json"
    write_json(path, {"status": "valid"})

    with pytest.raises(TypeError):
        write_json(path, {"invalid": object()})

    assert read_json(path) == {"status": "valid"}
    assert not list(tmp_path.glob("*.tmp"))


def test_sha256_helpers(tmp_path: Path) -> None:
    text = "anime storyboard"
    path = tmp_path / "story.md"
    path.write_text(text, encoding="utf-8")
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()

    assert sha256_text(text) == expected
    assert sha256_file(path) == expected
