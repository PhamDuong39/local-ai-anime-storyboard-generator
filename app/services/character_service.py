import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Sequence

from PIL import Image, UnidentifiedImageError

from app.core.errors import AppError
from app.core.file_io import read_json_model, write_json
from app.core.paths import characters_dir, metadata_path
from app.schemas.character import (
    CharacterMetadata,
    CharacterReference,
    CharacterStatus,
)
from app.schemas.project import ProjectMetadata, ProjectStatus


ACCEPTED_CHARACTER_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
MIN_RECOMMENDED_DIMENSION = 512
_SIMPLE_CHARACTER_NAME = re.compile(r"^[\w -]+$", re.UNICODE)


@dataclass(frozen=True)
class CharacterUpload:
    filename: str | None
    content: bytes | None


@dataclass(frozen=True)
class ValidatedCharacterUpload:
    reference: CharacterReference
    content: bytes


def _safe_original_filename(filename: str) -> str:
    return Path(filename.replace("\\", "/")).name


class CharacterService:
    def __init__(self, projects_root: str | Path) -> None:
        self.projects_root = Path(projects_root)

    def validate_character_upload(
        self, filename: str | None, content: bytes | None
    ) -> ValidatedCharacterUpload:
        if not filename or content is None:
            raise AppError(
                code="CHARACTER_FILE_REQUIRED",
                message="Choose at least one character reference image to continue.",
                http_status=400,
            )

        original_filename = _safe_original_filename(filename)
        extension = Path(original_filename).suffix.lower()
        name = Path(original_filename).stem.strip()
        if extension not in ACCEPTED_CHARACTER_EXTENSIONS:
            raise AppError(
                code="UNSUPPORTED_CHARACTER_IMAGE_TYPE",
                message=(
                    "This file type is not supported for character references. "
                    "Please upload a PNG, JPG, JPEG, or WEBP image."
                ),
                http_status=400,
                details={"received_filename": original_filename},
            )
        if not name or name in {".", ".."}:
            raise AppError(
                code="INVALID_CHARACTER_FILENAME",
                message=(
                    "This character filename is not valid. Rename it to the "
                    "character name, for example Akira.png, and upload it again."
                ),
                http_status=400,
            )
        if not content:
            raise AppError(
                code="CHARACTER_IMAGE_EMPTY",
                message="This character image is empty. Please upload another image.",
                http_status=400,
            )

        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                image_format = image.format
                image.load()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise AppError(
                code="CORRUPT_CHARACTER_IMAGE",
                message=(
                    "This image could not be read. Please upload a different "
                    "character reference image."
                ),
                http_status=400,
                details={"received_filename": original_filename},
            ) from exc

        mime_type = Image.MIME.get(image_format or "")
        if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise AppError(
                code="UNSUPPORTED_CHARACTER_IMAGE_TYPE",
                message=(
                    "This file type is not supported for character references. "
                    "Please upload a PNG, JPG, JPEG, or WEBP image."
                ),
                http_status=400,
            )

        warnings: list[str] = []
        if width < MIN_RECOMMENDED_DIMENSION or height < MIN_RECOMMENDED_DIMENSION:
            warnings.append("LOW_RESOLUTION")
        if extension != ".png":
            warnings.append("NON_PREFERRED_FORMAT")
        if not _SIMPLE_CHARACTER_NAME.fullmatch(name):
            warnings.append("FILENAME_MISMATCH_POSSIBLE")

        reference = CharacterReference(
            name=name,
            original_filename=original_filename,
            stored_path=f"input/characters/{original_filename}",
            mime_type=mime_type,
            width=width,
            height=height,
            file_size_bytes=len(content),
            is_full_body_expected=True,
            consistency_method="ip-adapter-faceid",
            status=(CharacterStatus.WARNING if warnings else CharacterStatus.VALID),
            warnings=warnings,
        )
        return ValidatedCharacterUpload(reference=reference, content=content)

    def save_characters(
        self, project_id: str, uploads: Sequence[CharacterUpload]
    ) -> CharacterMetadata:
        project_file = metadata_path(self.projects_root, project_id, "project.json")
        if not project_file.is_file():
            raise AppError(
                code="PROJECT_NOT_FOUND",
                message="This project could not be found.",
                http_status=404,
            )
        if not uploads:
            raise AppError(
                code="CHARACTER_FILE_REQUIRED",
                message="Choose at least one character reference image to continue.",
                http_status=400,
            )

        validated = [
            self.validate_character_upload(upload.filename, upload.content)
            for upload in uploads
        ]
        seen_names: dict[str, str] = {}
        for item in validated:
            folded_name = item.reference.name.casefold()
            if folded_name in seen_names:
                raise AppError(
                    code="DUPLICATE_CHARACTER_NAME",
                    message=(
                        "Two uploaded files map to the same character name: "
                        f"{item.reference.name}. Please keep only one image for "
                        "each character."
                    ),
                    http_status=400,
                    details={"character_name": item.reference.name},
                )
            seen_names[folded_name] = item.reference.original_filename

        metadata = CharacterMetadata(
            characters=[item.reference for item in validated]
        )
        destination_dir = characters_dir(self.projects_root, project_id)
        temporary_paths: list[tuple[Path, Path]] = []
        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
            for item in validated:
                destination = destination_dir / item.reference.original_filename
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=destination_dir,
                    prefix=f".{destination.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(temporary_file.name)
                    temporary_file.write(item.content)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())
                temporary_paths.append((temporary_path, destination))

            for temporary_path, destination in temporary_paths:
                os.replace(temporary_path, destination)

            write_json(
                metadata_path(self.projects_root, project_id, "characters.json"),
                metadata,
            )
            project = read_json_model(project_file, ProjectMetadata)
            project.status = ProjectStatus.CHARACTERS_UPLOADED
            project.updated_at = datetime.now(timezone.utc)
            write_json(project_file, project)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                code="CHARACTER_SAVE_FAILED",
                message=(
                    "The character images could not be saved locally. "
                    "Check the project folder and try again."
                ),
                http_status=500,
            ) from exc
        finally:
            for temporary_path, _ in temporary_paths:
                temporary_path.unlink(missing_ok=True)

        return metadata

    def get_characters(self, project_id: str) -> CharacterMetadata | None:
        project_file = metadata_path(self.projects_root, project_id, "project.json")
        if not project_file.is_file():
            raise AppError(
                code="PROJECT_NOT_FOUND",
                message="This project could not be found.",
                http_status=404,
            )

        characters_file = metadata_path(
            self.projects_root, project_id, "characters.json"
        )
        if not characters_file.exists():
            return None
        try:
            return read_json_model(characters_file, CharacterMetadata)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="CHARACTER_READ_FAILED",
                message=(
                    "The saved character list could not be read. "
                    "Please upload the character images again."
                ),
                http_status=500,
            ) from exc
