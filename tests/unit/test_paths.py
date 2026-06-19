from pathlib import Path

import pytest

from app.core.paths import (
    UnsafePathError,
    characters_dir,
    metadata_path,
    output_images_dir,
    project_relative_path,
    project_root,
    story_path,
    validate_project_id,
)


def test_valid_project_paths_stay_under_projects_root(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    project_id = validate_project_id("akira-episode-1-a7f3c2")

    root = project_root(projects_root, project_id)

    assert root == (projects_root / project_id).resolve()
    assert metadata_path(projects_root, project_id, "project.json").is_relative_to(root)
    assert story_path(projects_root, project_id).is_relative_to(root)
    assert characters_dir(projects_root, project_id).is_relative_to(root)
    assert output_images_dir(projects_root, project_id).is_relative_to(root)


@pytest.mark.parametrize(
    "project_id",
    ["../project", "project/name", r"project\\name", "/absolute", "ab", "UPPER"],
)
def test_unsafe_project_id_is_rejected(project_id: str) -> None:
    with pytest.raises(UnsafePathError):
        validate_project_id(project_id)


def test_metadata_filename_rejects_path_segments(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        metadata_path(tmp_path, "valid-project", "../project.json")


def test_project_relative_path_returns_portable_path(tmp_path: Path) -> None:
    path = story_path(tmp_path, "valid-project")

    assert project_relative_path(tmp_path, "valid-project", path) == "input/story.md"


def test_project_relative_path_rejects_outside_path(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        project_relative_path(tmp_path, "valid-project", tmp_path / "outside.txt")
