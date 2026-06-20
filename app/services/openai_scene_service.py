import re
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.core.file_io import read_json_model, write_json
from app.core.paths import metadata_path
from app.schemas.project import ProjectMetadata, ProjectStatus
from app.schemas.scene import Scene, SceneList, SceneStatus
from app.services.character_service import CharacterService
from app.services.scene_service import SceneService
from app.services.story_service import StoryService


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_MARKDOWN_HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)


class OpenAISceneService:
    """Split stories into scenes, using a deterministic local mock for the MVP shell."""

    def __init__(self, projects_root: str | Path, *, mock_mode: bool = True) -> None:
        self.projects_root = Path(projects_root)
        self.mock_mode = mock_mode
        self.story_service = StoryService(self.projects_root)
        self.character_service = CharacterService(self.projects_root)
        self.scene_service = SceneService(self.projects_root)

    def split_story_into_scenes(self, project_id: str) -> SceneList:
        if not self.mock_mode:
            raise AppError(
                code="OPENAI_SCENE_SERVICE_NOT_READY",
                message=(
                    "Real OpenAI scene splitting is not available yet. "
                    "Enable mock mode to continue testing the workflow."
                ),
                http_status=503,
            )

        stored_story = self.story_service.get_story(project_id)
        if stored_story is None:
            raise AppError(
                code="STORY_NOT_FOUND",
                message="Upload a story before splitting it into scenes.",
                http_status=409,
            )

        character_metadata = self.character_service.get_characters(project_id)
        character_names = (
            [character.name for character in character_metadata.characters]
            if character_metadata is not None
            else []
        )
        excerpts = self._story_excerpts(stored_story.normalized_text)
        scenes = [
            self._mock_scene(index, excerpt, character_names)
            for index, excerpt in enumerate(excerpts, start=1)
        ]
        scene_list = SceneList(
            project_id=project_id,
            story_title=self._story_title(stored_story.normalized_text),
            language="unknown",
            scene_count=len(scenes),
            scenes=scenes,
        )

        saved = self.scene_service.save_scenes(project_id, scene_list)
        self._update_project_status(project_id, ProjectStatus.SCENES_GENERATED)
        return saved

    @staticmethod
    def _story_title(story_text: str) -> str | None:
        match = _MARKDOWN_HEADING.search(story_text)
        return match.group(1).strip() if match else None

    @staticmethod
    def _story_excerpts(story_text: str) -> list[str]:
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", story_text)
            if paragraph.strip() and not paragraph.lstrip().startswith("#")
        ]
        units = paragraphs or [story_text.strip()]
        if len(units) == 1:
            sentences = [
                sentence.strip()
                for sentence in _SENTENCE_BOUNDARY.split(units[0])
                if sentence.strip()
            ]
            if len(sentences) >= 2:
                units = sentences

        scene_count = 3 if len(units) >= 3 else 2
        groups: list[list[str]] = [[] for _ in range(scene_count)]
        for index, unit in enumerate(units):
            group_index = min(index * scene_count // len(units), scene_count - 1)
            groups[group_index].append(unit)

        fallback = units[-1]
        return ["\n\n".join(group) if group else fallback for group in groups]

    @staticmethod
    def _mock_scene(
        scene_number: int, excerpt: str, character_names: list[str]
    ) -> Scene:
        labels = ("Story opening", "Story development", "Story conclusion")
        title = labels[min(scene_number - 1, len(labels) - 1)]
        detected_names = [
            name for name in character_names if name.casefold() in excerpt.casefold()
        ]
        # The mock should exercise character-aware UI even when a short excerpt does
        # not repeat every uploaded name. Real detection replaces this in M8.
        characters = detected_names or list(character_names)
        concise_excerpt = excerpt[:600].strip()
        summary_source = re.sub(r"\s+", " ", excerpt).strip()
        summary = summary_source[:280].rstrip()
        continuity_notes = [
            f"Keep {name}'s outfit and visual identity consistent with the reference."
            for name in characters
        ]
        return Scene(
            scene_id=f"scene_{scene_number:03d}",
            scene_number=scene_number,
            title=title,
            source_excerpt=concise_excerpt,
            summary=summary,
            characters=characters,
            location="story setting",
            time_of_day="unknown",
            mood="cinematic",
            main_action=summary,
            camera_shot="wide shot",
            camera_angle="eye level",
            visual_details=[
                "anime storyboard composition",
                "clear character staging",
                "environment matching the story excerpt",
            ],
            continuity_notes=continuity_notes,
            status=SceneStatus.DRAFT,
        )

    def _update_project_status(
        self, project_id: str, status: ProjectStatus
    ) -> None:
        project_file = metadata_path(self.projects_root, project_id, "project.json")
        try:
            project = read_json_model(project_file, ProjectMetadata)
            project.status = status
            project.updated_at = datetime.now(timezone.utc)
            write_json(project_file, project)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="SCENE_SPLIT_FAILED",
                message="The scenes were created but the project could not be updated.",
                http_status=500,
            ) from exc
