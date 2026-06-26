import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.file_io import read_json_model, write_json
from app.core.paths import metadata_path
from app.schemas.project import ProjectMetadata, ProjectStatus
from app.schemas.scene import Scene, SceneList, SceneStatus
from app.services.character_service import CharacterService
from app.services.openai_client import OpenAIClient
from app.services.scene_service import SceneService
from app.services.story_service import StoryService


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_MARKDOWN_HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)


class SceneOpenAIResponseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(min_length=1)
    scene_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=80)
    source_excerpt: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    characters: list[str]
    location: str = Field(min_length=1)
    time_of_day: str = Field(min_length=1)
    mood: str = Field(min_length=1)
    main_action: str = Field(min_length=1)
    camera_shot: str = Field(min_length=1)
    camera_angle: str = Field(min_length=1)
    visual_details: list[str] = Field(min_length=3, max_length=8)
    continuity_notes: list[str]
    status: str = Field(min_length=1)


class SceneOpenAIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    story_title: str | None
    language: str = Field(min_length=1)
    scene_count: int = Field(ge=1)
    scenes: list[SceneOpenAIResponseItem] = Field(min_length=1)


class SceneOpenAIClient(Protocol):
    def parse_json(
        self,
        *,
        model: str,
        instructions: str,
        payload: dict[str, Any],
        response_model: type[SceneOpenAIResponse],
        failure_code: str,
        failure_message: str,
        invalid_response_code: str | None = None,
        invalid_response_message: str | None = None,
    ) -> SceneOpenAIResponse: ...


class OpenAISceneService:
    """Split stories into scenes with real OpenAI or the deterministic mock path."""

    def __init__(
        self,
        projects_root: str | Path,
        *,
        mock_mode: bool = True,
        model: str | None = None,
        api_key: SecretStr | str | None = None,
        openai_client: SceneOpenAIClient | None = None,
        context_token_limit: int | None = None,
        request_overhead_tokens: int | None = None,
    ) -> None:
        self.projects_root = Path(projects_root)
        self.mock_mode = mock_mode
        settings = get_settings()
        self.model = model or settings.openai_scene_model
        self.openai_client = openai_client or OpenAIClient(
            api_key if api_key is not None else settings.openai_api_key
        )
        self.context_token_limit = (
            context_token_limit or settings.openai_context_token_limit
        )
        self.request_overhead_tokens = (
            request_overhead_tokens or settings.openai_request_overhead_tokens
        )
        self.story_service = StoryService(self.projects_root)
        self.character_service = CharacterService(self.projects_root)
        self.scene_service = SceneService(self.projects_root)

    def split_story_into_scenes(self, project_id: str) -> SceneList:
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
        if not self.mock_mode:
            return self._split_with_openai(
                project_id, stored_story.normalized_text, character_names
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

    def _split_with_openai(
        self, project_id: str, story_text: str, character_names: list[str]
    ) -> SceneList:
        self._check_context_budget(story_text)
        payload = {
            "project_id": project_id,
            "known_characters": character_names,
            "story_text": story_text,
            "requirements": {
                "output_format": "json_only",
                "phase": "image_only_storyboard",
                "preserve_order": True,
                "require_visual_scenes": True,
                "avoid_dialogue_text_in_images": True,
            },
        }
        instructions = (
            "You are an anime storyboard planner. Convert a free-form story into "
            "an ordered list of visual scenes for image generation. Each scene must "
            "represent one clear visual moment. Preserve story order. Do not invent "
            "major plot events. Return JSON only."
        )
        try:
            response = self.openai_client.parse_json(
                model=self.model,
                instructions=instructions,
                payload=payload,
                response_model=SceneOpenAIResponse,
                failure_code="SCENE_SPLIT_FAILED",
                failure_message=(
                    "OpenAI could not split the story into scenes. Please retry."
                ),
                invalid_response_code="SCENE_JSON_INVALID",
                invalid_response_message=(
                    "OpenAI returned scene data that could not be parsed. Please retry."
                ),
            )
            scene_list = self._scene_response_to_scene_list(project_id, response)
            saved = self.scene_service.save_scenes(project_id, scene_list)
            self._update_project_status(project_id, ProjectStatus.SCENES_GENERATED)
            return saved
        except AppError as exc:
            self._try_update_project_status(
                project_id, ProjectStatus.SCENE_SPLITTING_FAILED
            )
            if exc.code == "SCENE_SAVE_FAILED":
                raise AppError(
                    code="METADATA_WRITE_FAILED",
                    message="The scene list could not be saved locally. Please try again.",
                    http_status=500,
                ) from exc
            raise

    def _check_context_budget(self, story_text: str) -> None:
        estimated_tokens = self.request_overhead_tokens + max(1, len(story_text) // 3)
        if estimated_tokens > self.context_token_limit:
            raise AppError(
                code="STORY_TOO_LARGE_FOR_MODEL",
                message=(
                    "This story is too large for the configured OpenAI model. "
                    "Shorten the story or split it into a smaller project."
                ),
                http_status=400,
                details={
                    "estimated_tokens": estimated_tokens,
                    "context_token_limit": self.context_token_limit,
                },
            )

    @staticmethod
    def _scene_response_to_scene_list(
        project_id: str, response: SceneOpenAIResponse
    ) -> SceneList:
        try:
            scenes = [
                Scene(
                    scene_id=f"scene_{index:03d}",
                    scene_number=index,
                    title=item.title.strip(),
                    source_excerpt=item.source_excerpt.strip(),
                    summary=item.summary.strip(),
                    characters=[
                        name.strip() for name in item.characters if name.strip()
                    ],
                    location=item.location.strip(),
                    time_of_day=item.time_of_day.strip(),
                    mood=item.mood.strip(),
                    main_action=item.main_action.strip(),
                    camera_shot=item.camera_shot.strip(),
                    camera_angle=item.camera_angle.strip(),
                    visual_details=[
                        detail.strip()
                        for detail in item.visual_details
                        if detail.strip()
                    ],
                    continuity_notes=[
                        note.strip() for note in item.continuity_notes if note.strip()
                    ],
                    status=SceneStatus.DRAFT,
                )
                for index, item in enumerate(response.scenes, start=1)
            ]
            return SceneList(
                project_id=project_id,
                story_title=response.story_title,
                language=response.language,
                scene_count=len(scenes),
                scenes=scenes,
            )
        except ValidationError as exc:
            raise AppError(
                code="SCENE_SCHEMA_INVALID",
                message=(
                    "OpenAI returned scene data that did not match the required schema. "
                    "Please retry scene splitting."
                ),
                http_status=502,
            ) from exc

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

    def _update_project_status(self, project_id: str, status: ProjectStatus) -> None:
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

    def _try_update_project_status(
        self, project_id: str, status: ProjectStatus
    ) -> None:
        try:
            self._update_project_status(project_id, status)
        except AppError:
            return
