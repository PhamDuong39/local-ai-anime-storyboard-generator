import hashlib

import pytest

from app.core.errors import AppError
from app.core.file_io import read_json, write_json
from app.schemas.project import ProjectStatus
from app.services.project_service import ProjectService
from app.services.story_service import StoryService, compute_story_hash


def make_project(tmp_path):
    projects_root = tmp_path / "projects"
    project = ProjectService(
        projects_root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("Akira Episode 1", "youtube_standard")
    return projects_root, project


def assert_error(service, filename, content, code) -> None:
    with pytest.raises(AppError) as caught:
        service.validate_story_upload(filename, content)
    assert caught.value.code == code


@pytest.mark.parametrize("filename", ["story.txt", "story.pdf", "story"])
def test_rejects_unsupported_extension(tmp_path, filename) -> None:
    assert_error(
        StoryService(tmp_path), filename, b"A story", "STORY_UNSUPPORTED_FILE_TYPE"
    )


def test_rejects_non_utf8_content(tmp_path) -> None:
    assert_error(
        StoryService(tmp_path), "story.md", b"\xff\xfe", "STORY_INVALID_ENCODING"
    )


@pytest.mark.parametrize("content", [b"", b" \r\n\t "])
def test_rejects_empty_story(tmp_path, content) -> None:
    assert_error(StoryService(tmp_path), "story.md", content, "STORY_EMPTY")


def test_rejects_binary_looking_content(tmp_path) -> None:
    assert_error(
        StoryService(tmp_path),
        "story.md",
        b"Akira enters\x00\x01the room.",
        "STORY_BINARY_CONTENT_DETECTED",
    )


def test_rejects_file_over_one_megabyte(tmp_path) -> None:
    assert_error(
        StoryService(tmp_path),
        "story.md",
        b"a" * (1024 * 1024 + 1),
        "STORY_TOO_LARGE",
    )


def test_rejects_more_than_120000_normalized_characters(tmp_path) -> None:
    assert_error(
        StoryService(tmp_path),
        "story.md",
        b"a" * 120_001,
        "STORY_TOO_LARGE",
    )


def test_content_hash_uses_normalized_text() -> None:
    normalized = "# Episode 1\n\nAkira enters."
    expected = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    assert compute_story_hash(normalized) == f"sha256:{expected}"


def test_valid_story_is_normalized_saved_and_updates_project(tmp_path) -> None:
    projects_root, project = make_project(tmp_path)
    service = StoryService(projects_root)

    metadata = service.save_story(
        project.project_id,
        r"C:\uploads\Episode One.MD",
        b"\xef\xbb\xbf# Episode 1\r\n\r\nAkira enters.  \r\n",
    )
    root = projects_root / project.project_id

    assert (root / "input/story.md").read_text(encoding="utf-8") == (
        "# Episode 1\n\nAkira enters."
    )
    assert metadata.original_filename == "Episode One.MD"
    assert metadata.story_char_count == len("# Episode 1\n\nAkira enters.")
    assert metadata.content_hash.startswith("sha256:")
    assert read_json(root / "metadata/story.json")["story_char_count"] == (
        metadata.story_char_count
    )
    assert read_json(root / "metadata/project.json")["status"] == (
        ProjectStatus.STORY_UPLOADED.value
    )


def test_changed_story_resets_derived_metadata_but_preserves_images(tmp_path) -> None:
    projects_root, project = make_project(tmp_path)
    service = StoryService(projects_root)
    service.save_story(project.project_id, "story.md", b"First story")
    root = projects_root / project.project_id
    old_story_hash = read_json(root / "metadata/story.json")["content_hash"]

    for relative_path in (
        "metadata/scenes.json",
        "metadata/prompts.json",
        "metadata/generation_status.json",
        "outputs/manifest.json",
    ):
        write_json(root / relative_path, {"old": True})
    image = root / "outputs/images/001_old.png"
    image.write_bytes(b"old image")

    service.save_story(project.project_id, "replacement.md", b"Replacement story")

    for relative_path in (
        "metadata/scenes.json",
        "metadata/prompts.json",
        "metadata/generation_status.json",
    ):
        assert not (root / relative_path).exists()
    assert not (root / "outputs/manifest.json").exists()
    stale_manifest = root / (
        f"outputs/manifest.stale-{old_story_hash.removeprefix('sha256:')[:12]}.json"
    )
    assert read_json(stale_manifest) == {"old": True}
    assert image.read_bytes() == b"old image"


def test_identical_story_keeps_derived_metadata(tmp_path) -> None:
    projects_root, project = make_project(tmp_path)
    service = StoryService(projects_root)
    service.save_story(project.project_id, "story.md", b"Same story")
    scenes_path = projects_root / project.project_id / "metadata/scenes.json"
    write_json(scenes_path, {"keep": True})

    service.save_story(project.project_id, "renamed.md", b"Same story")

    assert read_json(scenes_path) == {"keep": True}
