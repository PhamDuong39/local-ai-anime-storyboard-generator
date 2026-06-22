from datetime import datetime, timezone
from pathlib import Path

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
from app.services.prompt_service import PromptService
from app.services.scene_service import SceneService


DEFAULT_NEGATIVE_PROMPT = (
    "low quality, blurry, pixelated, distorted face, asymmetrical eyes, "
    "bad anatomy, bad hands, extra fingers, missing fingers, duplicate character, "
    "inconsistent outfit, inconsistent hairstyle, text, subtitle, speech bubble, "
    "watermark, logo, cropped face, cropped body"
)


class OpenAIPromptService:
    """Generate deterministic mock prompts until the real OpenAI path is added."""

    def __init__(self, projects_root: str | Path, *, mock_mode: bool = True) -> None:
        self.projects_root = Path(projects_root)
        self.mock_mode = mock_mode
        self.scene_service = SceneService(self.projects_root)
        self.character_service = CharacterService(self.projects_root)
        self.prompt_service = PromptService(self.projects_root)

    def generate_prompts(self, project_id: str) -> PromptList:
        if not self.mock_mode:
            raise AppError(
                code="OPENAI_PROMPT_SERVICE_NOT_READY",
                message=(
                    "Real OpenAI prompt generation is not available yet. "
                    "Enable mock mode to continue testing the workflow."
                ),
                http_status=503,
            )

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
