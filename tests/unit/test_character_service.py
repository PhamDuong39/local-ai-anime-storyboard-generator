from io import BytesIO

import pytest
from PIL import Image

from app.core.errors import AppError
from app.core.file_io import read_json
from app.schemas.project import ProjectStatus
from app.services.character_service import CharacterService, CharacterUpload
from app.services.project_service import ProjectService


def make_project(tmp_path):
    projects_root = tmp_path / "projects"
    project = ProjectService(
        projects_root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("Akira Episode 1", "youtube_standard")
    return projects_root, project


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (768, 1024)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color="navy").save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("filename", "image_format", "mime_type"),
    [
        ("Akira.png", "PNG", "image/png"),
        ("Akira.jpg", "JPEG", "image/jpeg"),
        ("Akira.jpeg", "JPEG", "image/jpeg"),
        ("Akira.webp", "WEBP", "image/webp"),
    ],
)
def test_accepts_supported_extensions(tmp_path, filename, image_format, mime_type) -> None:
    result = CharacterService(tmp_path).validate_character_upload(
        filename, image_bytes(image_format)
    )

    assert result.reference.name == "Akira"
    assert result.reference.mime_type == mime_type
    assert result.reference.consistency_method == "ip-adapter-faceid"


@pytest.mark.parametrize("filename", ["Akira.gif", "Akira.bmp", "Akira.svg"])
def test_rejects_unsupported_extensions(tmp_path, filename) -> None:
    with pytest.raises(AppError) as caught:
        CharacterService(tmp_path).validate_character_upload(filename, b"image")

    assert caught.value.code == "UNSUPPORTED_CHARACTER_IMAGE_TYPE"


def test_rejects_duplicate_stems_case_insensitively(tmp_path) -> None:
    projects_root, project = make_project(tmp_path)
    service = CharacterService(projects_root)

    with pytest.raises(AppError) as caught:
        service.save_characters(
            project.project_id,
            [
                CharacterUpload("Akira.png", image_bytes()),
                CharacterUpload("akira.jpg", image_bytes("JPEG")),
            ],
        )

    assert caught.value.code == "DUPLICATE_CHARACTER_NAME"
    assert not (
        projects_root / project.project_id / "metadata/characters.json"
    ).exists()


def test_rejects_corrupt_image(tmp_path) -> None:
    with pytest.raises(AppError) as caught:
        CharacterService(tmp_path).validate_character_upload(
            "Akira.png", b"not an image"
        )

    assert caught.value.code == "CORRUPT_CHARACTER_IMAGE"


def test_saves_originals_metadata_warnings_and_project_status(tmp_path) -> None:
    projects_root, project = make_project(tmp_path)
    service = CharacterService(projects_root)
    content = image_bytes(size=(400, 700))

    metadata = service.save_characters(
        project.project_id,
        [CharacterUpload(r"C:\uploads\Akira.png", content)],
    )
    root = projects_root / project.project_id
    stored = read_json(root / "metadata/characters.json")

    assert (root / "input/characters/Akira.png").read_bytes() == content
    assert metadata.version == 1
    assert stored["characters"][0]["name"] == "Akira"
    assert stored["characters"][0]["stored_path"] == (
        "input/characters/Akira.png"
    )
    assert stored["characters"][0]["status"] == "warning"
    assert stored["characters"][0]["warnings"] == ["LOW_RESOLUTION"]
    assert stored["characters"][0]["consistency_method"] == (
        "ip-adapter-faceid"
    )
    assert read_json(root / "metadata/project.json")["status"] == (
        ProjectStatus.CHARACTERS_UPLOADED.value
    )
