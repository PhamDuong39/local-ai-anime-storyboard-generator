import re
from pathlib import Path, PurePath


PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")


class UnsafePathError(ValueError):
    """Raised when user-controlled path input is unsafe."""


def validate_project_id(project_id: str) -> str:
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise UnsafePathError(
            "Project ID must be 3-81 lowercase URL-safe letters, numbers, or hyphens."
        )
    return project_id


def _resolved_root(projects_root: str | Path) -> Path:
    return Path(projects_root).expanduser().resolve()


def _ensure_within(path: Path, parent: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise UnsafePathError(
            "Resolved path is outside the allowed project folder."
        ) from exc
    return resolved


def project_root(projects_root: str | Path, project_id: str) -> Path:
    safe_id = validate_project_id(project_id)
    root = _resolved_root(projects_root)
    return _ensure_within(root / safe_id, root)


def metadata_dir(projects_root: str | Path, project_id: str) -> Path:
    return project_root(projects_root, project_id) / "metadata"


def metadata_path(projects_root: str | Path, project_id: str, filename: str) -> Path:
    if (
        not filename
        or PurePath(filename).name != filename
        or "/" in filename
        or "\\" in filename
        or filename in {".", ".."}
    ):
        raise UnsafePathError("Metadata filename must be a plain filename.")
    return _ensure_within(
        metadata_dir(projects_root, project_id) / filename,
        metadata_dir(projects_root, project_id),
    )


def story_path(projects_root: str | Path, project_id: str) -> Path:
    return project_root(projects_root, project_id) / "input" / "story.md"


def characters_dir(projects_root: str | Path, project_id: str) -> Path:
    return project_root(projects_root, project_id) / "input" / "characters"


def output_images_dir(projects_root: str | Path, project_id: str) -> Path:
    return project_root(projects_root, project_id) / "outputs" / "images"


def project_relative_path(
    projects_root: str | Path, project_id: str, path: str | Path
) -> str:
    root = project_root(projects_root, project_id)
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    safe_path = _ensure_within(candidate, root)
    return safe_path.relative_to(root).as_posix()


# Explicit builder aliases keep call sites readable without duplicating logic.
get_project_root = project_root
get_metadata_dir = metadata_dir
get_metadata_path = metadata_path
get_story_path = story_path
get_characters_dir = characters_dir
get_output_images_dir = output_images_dir
to_project_relative_path = project_relative_path
