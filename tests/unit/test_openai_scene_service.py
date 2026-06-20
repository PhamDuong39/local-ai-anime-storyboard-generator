from pathlib import Path

from app.core.file_io import read_json, write_json
from app.schemas.character import CharacterMetadata, CharacterReference, CharacterStatus
from app.schemas.project import ProjectStatus
from app.schemas.scene import SceneStatus
from app.services.openai_scene_service import OpenAISceneService
from app.services.project_service import ProjectService
from app.services.story_service import StoryService


STORY = b"""# The Empty School

Akira enters the abandoned school at dusk. The rusted gate closes behind him.

Hana appears beside a dark hallway and warns Akira to leave.

Together they hear footsteps approaching from the empty classroom."""


def make_project(tmp_path: Path) -> tuple[Path, str]:
    projects_root = tmp_path / "projects"
    project = ProjectService(
        projects_root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("The Empty School", "youtube_standard")
    StoryService(projects_root).save_story(project.project_id, "story.md", STORY)
    return projects_root, project.project_id


def add_character_metadata(projects_root: Path, project_id: str) -> None:
    characters = CharacterMetadata(
        characters=[
            CharacterReference(
                name=name,
                original_filename=f"{name}.png",
                stored_path=f"input/characters/{name}.png",
                mime_type="image/png",
                width=1024,
                height=1536,
                file_size_bytes=100,
                status=CharacterStatus.VALID,
            )
            for name in ("Akira", "Hana")
        ]
    )
    write_json(
        projects_root / project_id / "metadata" / "characters.json", characters
    )


def test_mock_split_is_deterministic_valid_and_persisted(tmp_path) -> None:
    projects_root, project_id = make_project(tmp_path)
    add_character_metadata(projects_root, project_id)
    service = OpenAISceneService(projects_root, mock_mode=True)

    first = service.split_story_into_scenes(project_id)
    second = service.split_story_into_scenes(project_id)

    assert first == second
    assert first.story_title == "The Empty School"
    assert first.scene_count == 3
    assert [scene.scene_id for scene in first.scenes] == [
        "scene_001",
        "scene_002",
        "scene_003",
    ]
    assert all(scene.status is SceneStatus.DRAFT for scene in first.scenes)
    assert {name for scene in first.scenes for name in scene.characters} == {
        "Akira",
        "Hana",
    }
    assert read_json(
        projects_root / project_id / "metadata" / "scenes.json"
    ) == first.model_dump(mode="json")
    assert read_json(
        projects_root / project_id / "metadata" / "project.json"
    )["status"] == ProjectStatus.SCENES_GENERATED.value


def test_mock_split_creates_two_scenes_without_character_metadata(tmp_path) -> None:
    projects_root, project_id = make_project(tmp_path)
    short_story = b"Akira opens the door. He steps into the room."
    StoryService(projects_root).save_story(project_id, "story.md", short_story)

    result = OpenAISceneService(projects_root).split_story_into_scenes(project_id)

    assert result.scene_count == 2
    assert [scene.scene_number for scene in result.scenes] == [1, 2]
    assert all(scene.characters == [] for scene in result.scenes)
