import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.core.file_io import read_json_model, sha256_text, write_json
from app.core.paths import metadata_path, project_root, story_path
from app.schemas.project import ProjectMetadata, ProjectStatus
from app.schemas.story import StoryMetadata, StoryStatus


MAX_STORY_FILE_BYTES = 1024 * 1024
MAX_STORY_CHARACTERS = 120_000
_ALLOWED_CONTROL_CHARACTERS = {"\t", "\n", "\r"}


@dataclass(frozen=True)
class StoryValidationResult:
    original_filename: str
    normalized_text: str
    file_size_bytes: int
    story_char_count: int
    approx_word_count: int
    line_count: int
    content_hash: str


@dataclass(frozen=True)
class StoredStory:
    metadata: StoryMetadata
    normalized_text: str

    @property
    def preview(self) -> str:
        return self.normalized_text[:2000]


def normalize_story_text(raw_text: str) -> str:
    text = raw_text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        character
        for character in text
        if character in _ALLOWED_CONTROL_CHARACTERS
        or not unicodedata.category(character).startswith("C")
    )
    return text.strip()


def compute_story_hash(normalized_text: str) -> str:
    return f"sha256:{sha256_text(normalized_text)}"


def _safe_original_filename(filename: str) -> str:
    return Path(filename.replace("\\", "/")).name


def _looks_binary(text: str) -> bool:
    if "\x00" in text:
        return True
    if not text:
        return False
    control_count = sum(
        1
        for character in text
        if character not in _ALLOWED_CONTROL_CHARACTERS
        and unicodedata.category(character).startswith("C")
    )
    return control_count / len(text) > 0.01


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(text)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


class StoryService:
    def __init__(self, projects_root: str | Path) -> None:
        self.projects_root = Path(projects_root)

    def validate_story_upload(
        self, filename: str | None, content: bytes | None
    ) -> StoryValidationResult:
        if not filename or content is None:
            raise AppError(
                code="STORY_FILE_REQUIRED",
                message="Choose a Markdown .md story file to continue.",
                http_status=400,
            )

        original_filename = _safe_original_filename(filename)
        if not original_filename.lower().endswith(".md"):
            raise AppError(
                code="STORY_UNSUPPORTED_FILE_TYPE",
                message="Please upload a Markdown .md story file.",
                http_status=400,
                details={"received_filename": original_filename},
            )
        if len(content) > MAX_STORY_FILE_BYTES:
            raise AppError(
                code="STORY_TOO_LARGE",
                message=(
                    "This story file is too large for Phase 1. "
                    "Please upload a shorter .md file under 1 MB."
                ),
                http_status=400,
            )

        try:
            decoded_text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError(
                code="STORY_INVALID_ENCODING",
                message=(
                    "This story file could not be read as UTF-8 text. "
                    "Please save it as a UTF-8 .md file and upload again."
                ),
                http_status=400,
            ) from exc

        decoded_text_without_bom = decoded_text.removeprefix("\ufeff")
        if _looks_binary(decoded_text_without_bom):
            raise AppError(
                code="STORY_BINARY_CONTENT_DETECTED",
                message=(
                    "This file does not look like a text story. "
                    "Please upload a UTF-8 Markdown .md file."
                ),
                http_status=400,
            )

        normalized_text = normalize_story_text(decoded_text_without_bom)
        if not normalized_text:
            raise AppError(
                code="STORY_EMPTY",
                message="Your story file is empty. Please add story text and upload again.",
                http_status=400,
            )
        if len(normalized_text) > MAX_STORY_CHARACTERS:
            raise AppError(
                code="STORY_TOO_LARGE",
                message=(
                    "This story has more than 120,000 characters. "
                    "Please shorten it and upload again."
                ),
                http_status=400,
            )

        return StoryValidationResult(
            original_filename=original_filename,
            normalized_text=normalized_text,
            file_size_bytes=len(content),
            story_char_count=len(normalized_text),
            approx_word_count=len(re.findall(r"\S+", normalized_text)),
            line_count=normalized_text.count("\n") + 1,
            content_hash=compute_story_hash(normalized_text),
        )

    def save_story(
        self, project_id: str, filename: str | None, content: bytes | None
    ) -> StoryMetadata:
        project_file = metadata_path(self.projects_root, project_id, "project.json")
        if not project_file.is_file():
            raise AppError(
                code="PROJECT_NOT_FOUND",
                message="This project could not be found.",
                http_status=404,
            )

        validation = self.validate_story_upload(filename, content)
        old_hash = self._existing_story_hash(project_id)
        now = datetime.now(timezone.utc)
        metadata = StoryMetadata(
            story_status=StoryStatus.UPLOADED,
            original_filename=validation.original_filename,
            stored_path="input/story.md",
            file_size_bytes=validation.file_size_bytes,
            story_char_count=validation.story_char_count,
            approx_word_count=validation.approx_word_count,
            line_count=validation.line_count,
            uploaded_at=now,
            content_hash=validation.content_hash,
        )

        try:
            _atomic_write_text(
                story_path(self.projects_root, project_id), validation.normalized_text
            )
            write_json(
                metadata_path(self.projects_root, project_id, "story.json"), metadata
            )
            if old_hash is not None and old_hash != validation.content_hash:
                self._reset_derived_metadata(project_id, old_hash)

            project = read_json_model(project_file, ProjectMetadata)
            project.status = ProjectStatus.STORY_UPLOADED
            project.updated_at = now
            write_json(project_file, project)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                code="STORY_SAVE_FAILED",
                message=(
                    "The story could not be saved locally. "
                    "Check the project folder and try again."
                ),
                http_status=500,
            ) from exc

        return metadata

    def get_story(self, project_id: str) -> StoredStory | None:
        project_file = metadata_path(self.projects_root, project_id, "project.json")
        if not project_file.is_file():
            raise AppError(
                code="PROJECT_NOT_FOUND",
                message="This project could not be found.",
                http_status=404,
            )

        metadata_file = metadata_path(self.projects_root, project_id, "story.json")
        stored_story_file = story_path(self.projects_root, project_id)
        if not metadata_file.exists() and not stored_story_file.exists():
            return None
        if not metadata_file.is_file() or not stored_story_file.is_file():
            raise AppError(
                code="STORY_READ_FAILED",
                message=(
                    "The saved story could not be read. "
                    "Please upload the Markdown file again."
                ),
                http_status=500,
            )

        try:
            metadata = read_json_model(metadata_file, StoryMetadata)
            normalized_text = stored_story_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as exc:
            raise AppError(
                code="STORY_READ_FAILED",
                message=(
                    "The saved story could not be read. "
                    "Please upload the Markdown file again."
                ),
                http_status=500,
            ) from exc

        if compute_story_hash(normalized_text) != metadata.content_hash:
            raise AppError(
                code="STORY_READ_FAILED",
                message=(
                    "The saved story no longer matches its metadata. "
                    "Please upload the Markdown file again."
                ),
                http_status=500,
            )
        return StoredStory(metadata=metadata, normalized_text=normalized_text)

    def _existing_story_hash(self, project_id: str) -> str | None:
        path = metadata_path(self.projects_root, project_id, "story.json")
        if not path.is_file():
            return None
        return read_json_model(path, StoryMetadata).content_hash

    def _reset_derived_metadata(self, project_id: str, old_story_hash: str) -> None:
        for filename in ("scenes.json", "prompts.json", "generation_status.json"):
            metadata_path(self.projects_root, project_id, filename).unlink(
                missing_ok=True
            )

        # Keep prior output records and images, but move the current manifest aside so
        # later workflow steps cannot mistake it for output from the replacement story.
        outputs = project_root(self.projects_root, project_id) / "outputs"
        manifest = outputs / "manifest.json"
        if manifest.is_file():
            old_hash_suffix = old_story_hash.removeprefix("sha256:")[:12]
            os.replace(manifest, outputs / f"manifest.stale-{old_hash_suffix}.json")
