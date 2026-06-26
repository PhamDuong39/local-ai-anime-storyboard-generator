from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.file_io import read_json_model, write_json
from app.core.paths import metadata_path
from app.schemas.character import CharacterMetadata, CharacterReference
from app.schemas.project import ProjectMetadata, ProjectStatus
from app.schemas.prompt import (
    Prompt,
    PromptCharacter,
    PromptGenerationSettings,
    PromptList,
    PromptStatus,
)
from app.schemas.scene import Scene, SceneStatus
from app.services.character_service import CharacterService
from app.services.openai_client import OpenAIClient
from app.services.prompt_service import PromptService
from app.services.scene_service import SceneService


DEFAULT_NEGATIVE_PROMPT = (
    "low quality, blurry, pixelated, distorted face, asymmetrical eyes, "
    "bad anatomy, bad hands, extra fingers, missing fingers, duplicate character, "
    "inconsistent outfit, inconsistent hairstyle, text, subtitle, speech bubble, "
    "watermark, logo, cropped face, cropped body"
)


class PromptOpenAICharacter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    role_in_scene: str = Field(min_length=1)
    visual_priority: str = Field(min_length=1)


class PromptOpenAIItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(min_length=1)
    scene_number: int = Field(ge=1)
    positive_prompt: str = Field(min_length=1)
    negative_prompt: str = Field(min_length=1)
    characters: list[PromptOpenAICharacter]
    status: str = Field(min_length=1)


class PromptOpenAIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    prompts: list[PromptOpenAIItem] = Field(min_length=1)


class PromptOpenAIClient(Protocol):
    def parse_json(
        self,
        *,
        model: str,
        instructions: str,
        payload: dict[str, Any],
        response_model: type[PromptOpenAIResponse],
        failure_code: str,
        failure_message: str,
        invalid_response_code: str | None = None,
        invalid_response_message: str | None = None,
    ) -> PromptOpenAIResponse: ...


class OpenAIPromptService:
    """Generate prompts with real OpenAI or the deterministic mock path."""

    def __init__(
        self,
        projects_root: str | Path,
        *,
        mock_mode: bool = True,
        model: str | None = None,
        api_key: SecretStr | str | None = None,
        openai_client: PromptOpenAIClient | None = None,
    ) -> None:
        self.projects_root = Path(projects_root)
        self.mock_mode = mock_mode
        settings = get_settings()
        self.model = model or settings.openai_prompt_model
        self.openai_client = openai_client or OpenAIClient(
            api_key if api_key is not None else settings.openai_api_key
        )
        self.scene_service = SceneService(self.projects_root)
        self.character_service = CharacterService(self.projects_root)
        self.prompt_service = PromptService(self.projects_root)

    def generate_prompts(self, project_id: str) -> PromptList:
        project = self._require_project(project_id)
        scene_list = self.scene_service.get_scenes(project_id)
        if scene_list is None:
            raise AppError(
                code="SCENE_LIST_NOT_FOUND",
                message="Split and approve the story scenes before generating prompts.",
                http_status=404,
            )

        active_scenes = scene_list.active_scenes
        if not active_scenes or any(
            scene.status is not SceneStatus.APPROVED for scene in active_scenes
        ):
            raise AppError(
                code="SCENE_APPROVAL_REQUIRED",
                message="Approve every active scene before generating prompts.",
                http_status=409,
            )

        characters = self.character_service.get_characters(project_id)
        references = self._references_by_name(characters)
        if not self.mock_mode:
            return self._generate_with_openai(
                project_id=project_id,
                project=project,
                active_scenes=active_scenes,
                characters=characters,
                references=references,
            )

        prompts = [
            self._mock_prompt(scene, project, references) for scene in active_scenes
        ]
        prompt_list = PromptList(
            project_id=project_id,
            output_preset=project.output_preset,
            prompts=prompts,
        )

        saved = self.prompt_service.save_prompts(project_id, prompt_list)
        self._update_project_status(project_id, ProjectStatus.PROMPTS_GENERATED)
        return saved

    def _generate_with_openai(
        self,
        *,
        project_id: str,
        project: ProjectMetadata,
        active_scenes: list[Scene],
        characters: CharacterMetadata | None,
        references: dict[str, CharacterReference],
    ) -> PromptList:
        payload = {
            "project_id": project_id,
            "approved_scenes": [
                scene.model_dump(mode="json") for scene in active_scenes
            ],
            "characters": (
                [
                    character.model_dump(mode="json")
                    for character in characters.characters
                ]
                if characters is not None
                else []
            ),
            "output_preset": project.output_preset.model_dump(mode="json"),
            "character_consistency": {
                "method": "ip-adapter-faceid",
                "mode": "best_effort",
            },
        }
        instructions = (
            "You are an anime image prompt engineer for a local Diffusers pipeline. "
            "Convert approved storyboard scenes into concise image-generation prompts. "
            "Preserve character names and scene order. Do not create video prompts. "
            "Do not request speech bubbles, subtitles, watermarks, logos, or readable "
            "text. Return JSON only."
        )
        try:
            response = self.openai_client.parse_json(
                model=self.model,
                instructions=instructions,
                payload=payload,
                response_model=PromptOpenAIResponse,
                failure_code="PROMPT_GENERATION_FAILED",
                failure_message=(
                    "OpenAI could not generate image prompts. Please retry."
                ),
                invalid_response_code="PROMPT_JSON_INVALID",
                invalid_response_message=(
                    "OpenAI returned prompt data that could not be parsed. Please retry."
                ),
            )
            prompt_list = self._prompt_response_to_prompt_list(
                project_id=project_id,
                project=project,
                active_scenes=active_scenes,
                references=references,
                response=response,
            )
            saved = self.prompt_service.save_prompts(project_id, prompt_list)
            self._update_project_status(project_id, ProjectStatus.PROMPTS_GENERATED)
            return saved
        except AppError as exc:
            self._try_update_project_status(
                project_id, ProjectStatus.PROMPT_GENERATION_FAILED
            )
            if exc.code == "PROMPT_SAVE_FAILED":
                raise AppError(
                    code="METADATA_WRITE_FAILED",
                    message="The prompts could not be saved locally. Please try again.",
                    http_status=500,
                ) from exc
            raise

    @staticmethod
    def _references_by_name(
        metadata: CharacterMetadata | None,
    ) -> dict[str, CharacterReference]:
        if metadata is None:
            return {}
        return {
            character.name.casefold(): character for character in metadata.characters
        }

    @staticmethod
    def _mock_prompt(
        scene: Scene,
        project: ProjectMetadata,
        references: dict[str, CharacterReference],
    ) -> Prompt:
        character_names = ", ".join(scene.characters) or "no featured character"
        details = ", ".join(scene.visual_details)
        continuity = ", ".join(scene.continuity_notes)
        positive_parts = [
            "anime storyboard illustration",
            scene.camera_shot,
            scene.camera_angle,
            f"{character_names}: {scene.main_action}",
            scene.location,
            scene.time_of_day,
            f"{scene.mood} mood",
            details,
        ]
        if continuity:
            positive_parts.append(continuity)
        positive_parts.extend(
            [
                "cinematic lighting",
                "clean line art",
                "clear character staging",
                f"{project.output_preset.aspect_ratio} composition",
                f"{project.output_preset.width}x{project.output_preset.height} output",
            ]
        )

        prompt_characters = []
        for name in scene.characters:
            reference = references.get(name.casefold())
            if reference is not None:
                prompt_characters.append(
                    PromptCharacter(
                        name=reference.name,
                        reference_image_path=reference.stored_path,
                        consistency_method="ip-adapter-faceid",
                        role_in_scene="featured character",
                        visual_priority="high",
                    )
                )

        return Prompt(
            scene_id=scene.scene_id,
            scene_number=scene.scene_number,
            positive_prompt=", ".join(part for part in positive_parts if part),
            negative_prompt=DEFAULT_NEGATIVE_PROMPT,
            characters=prompt_characters,
            generation_settings=PromptGenerationSettings(
                width=project.output_preset.width,
                height=project.output_preset.height,
            ),
            status=PromptStatus.READY,
            manual_edit=False,
        )

    @staticmethod
    def _prompt_response_to_prompt_list(
        *,
        project_id: str,
        project: ProjectMetadata,
        active_scenes: list[Scene],
        references: dict[str, CharacterReference],
        response: PromptOpenAIResponse,
    ) -> PromptList:
        response_by_scene_id = {prompt.scene_id: prompt for prompt in response.prompts}
        expected_ids = [scene.scene_id for scene in active_scenes]
        if set(response_by_scene_id) != set(expected_ids):
            raise AppError(
                code="PROMPT_SCHEMA_INVALID",
                message="OpenAI must return exactly one prompt for every approved scene.",
                http_status=502,
            )

        try:
            prompts = []
            for scene in active_scenes:
                item = response_by_scene_id[scene.scene_id]
                prompt_characters = []
                for character in item.characters:
                    reference = references.get(character.name.casefold())
                    if reference is None:
                        continue
                    prompt_characters.append(
                        PromptCharacter(
                            name=reference.name,
                            reference_image_path=reference.stored_path,
                            consistency_method="ip-adapter-faceid",
                            role_in_scene=character.role_in_scene.strip(),
                            visual_priority=character.visual_priority.strip(),
                        )
                    )
                prompts.append(
                    Prompt(
                        scene_id=scene.scene_id,
                        scene_number=scene.scene_number,
                        positive_prompt=item.positive_prompt.strip(),
                        negative_prompt=item.negative_prompt.strip(),
                        characters=prompt_characters,
                        generation_settings=PromptGenerationSettings(
                            width=project.output_preset.width,
                            height=project.output_preset.height,
                            num_images=1,
                            seed=None,
                            guidance_scale=7.0,
                            num_inference_steps=30,
                        ),
                        status=PromptStatus.READY,
                        manual_edit=False,
                    )
                )
            return PromptList(
                project_id=project_id,
                output_preset=project.output_preset,
                prompts=prompts,
            )
        except ValidationError as exc:
            raise AppError(
                code="PROMPT_SCHEMA_INVALID",
                message=(
                    "OpenAI returned prompt data that did not match the required schema. "
                    "Please retry prompt generation."
                ),
                http_status=502,
            ) from exc

    def _require_project(self, project_id: str) -> ProjectMetadata:
        project_file = metadata_path(self.projects_root, project_id, "project.json")
        if not project_file.is_file():
            raise AppError(
                code="PROJECT_NOT_FOUND",
                message="This project could not be found.",
                http_status=404,
            )
        try:
            return read_json_model(project_file, ProjectMetadata)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="PROJECT_NOT_FOUND",
                message="This project could not be read.",
                http_status=404,
            ) from exc

    def _update_project_status(self, project_id: str, status: ProjectStatus) -> None:
        project_file = metadata_path(self.projects_root, project_id, "project.json")
        try:
            project = read_json_model(project_file, ProjectMetadata)
            project.status = status
            project.updated_at = datetime.now(timezone.utc)
            write_json(project_file, project)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="PROMPT_GENERATION_FAILED",
                message="The prompts were saved, but the project status could not be updated.",
                http_status=500,
            ) from exc

    def _try_update_project_status(
        self, project_id: str, status: ProjectStatus
    ) -> None:
        try:
            self._update_project_status(project_id, status)
        except AppError:
            return
