from pathlib import Path

from pydantic import ValidationError

from app.core.errors import AppError
from app.core.file_io import read_json_model, write_json
from app.core.paths import metadata_path
from app.schemas.project import ProjectMetadata
from app.schemas.prompt import Prompt, PromptList, PromptStatus
from app.schemas.scene import SceneList, SceneStatus


class PromptService:
    """Manage validated prompt metadata independently of an AI provider."""

    def __init__(self, projects_root: str | Path) -> None:
        self.projects_root = Path(projects_root)

    def save_prompts(self, project_id: str, prompt_list: PromptList) -> PromptList:
        project = self._require_project(project_id)
        if prompt_list.project_id != project_id:
            raise AppError(
                code="PROMPT_PROJECT_MISMATCH",
                message="The prompt list does not belong to this project.",
                http_status=400,
            )

        try:
            validated = PromptList.model_validate(prompt_list.model_dump(mode="json"))
        except ValidationError as exc:
            raise AppError(
                code="PROMPT_SCHEMA_INVALID",
                message="The prompt list is invalid. Review the prompts and try again.",
                http_status=422,
            ) from exc

        if validated.output_preset != project.output_preset:
            raise AppError(
                code="PROMPT_SCHEMA_INVALID",
                message="Prompt dimensions must match this project's output preset.",
                http_status=422,
            )

        self.validate_scene_mapping(project_id, validated)
        try:
            write_json(self._prompts_path(project_id), validated)
        except OSError as exc:
            raise AppError(
                code="PROMPT_SAVE_FAILED",
                message="The prompts could not be saved locally. Please try again.",
                http_status=500,
            ) from exc
        return validated

    def get_prompts(self, project_id: str) -> PromptList | None:
        self._require_project(project_id)
        prompts_file = self._prompts_path(project_id)
        if not prompts_file.is_file():
            return None
        try:
            return read_json_model(prompts_file, PromptList)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="PROMPT_SCHEMA_INVALID",
                message="The saved prompts are invalid. Generate the prompts again.",
                http_status=422,
            ) from exc

    def validate_scene_mapping(self, project_id: str, prompt_list: PromptList) -> None:
        scenes = self._require_scenes(project_id)
        approved_scenes = [
            scene for scene in scenes.scenes if scene.status is SceneStatus.APPROVED
        ]
        active_scenes = scenes.active_scenes
        if len(approved_scenes) != len(active_scenes):
            raise AppError(
                code="SCENE_APPROVAL_REQUIRED",
                message="Approve every active scene before creating prompts.",
                http_status=409,
            )

        expected = [(scene.scene_id, scene.scene_number) for scene in approved_scenes]
        actual = [
            (prompt.scene_id, prompt.scene_number) for prompt in prompt_list.prompts
        ]
        if actual != expected:
            raise AppError(
                code="PROMPT_SCHEMA_INVALID",
                message="Each approved scene must have exactly one prompt in scene order.",
                http_status=422,
            )

    def require_ready_prompts(self, project_id: str) -> PromptList:
        prompts = self.get_prompts(project_id)
        if prompts is None:
            raise AppError(
                code="PROMPTS_MISSING",
                message="Generate prompts for the approved scenes before continuing.",
                http_status=409,
            )
        self.validate_scene_mapping(project_id, prompts)
        if any(prompt.status is PromptStatus.STALE for prompt in prompts.prompts):
            raise AppError(
                code="PROMPT_STALE",
                message="A scene changed after its prompt was created. Regenerate stale prompts.",
                http_status=409,
            )
        if any(prompt.status is not PromptStatus.READY for prompt in prompts.prompts):
            raise AppError(
                code="PROMPT_SCHEMA_INVALID",
                message="Every prompt must be ready before image generation can start.",
                http_status=422,
            )
        return prompts

    def update_prompt(
        self,
        project_id: str,
        scene_id: str,
        *,
        positive_prompt: str,
        negative_prompt: str,
    ) -> Prompt:
        prompt_list = self.get_prompts(project_id)
        if prompt_list is None:
            raise AppError(
                code="PROMPTS_MISSING",
                message="Generate prompts before trying to edit them.",
                http_status=404,
            )

        updated_prompt: Prompt | None = None
        updated_prompts: list[Prompt] = []
        for prompt in prompt_list.prompts:
            if prompt.scene_id == scene_id:
                try:
                    updated_prompt = Prompt.model_validate(
                        {
                            **prompt.model_dump(mode="json"),
                            "positive_prompt": positive_prompt,
                            "negative_prompt": negative_prompt,
                            "status": PromptStatus.READY,
                            "manual_edit": True,
                        }
                    )
                except ValidationError as exc:
                    raise AppError(
                        code="PROMPT_UPDATE_INVALID",
                        message="Positive and negative prompts cannot be empty.",
                        http_status=400,
                    ) from exc
                prompt = updated_prompt
            updated_prompts.append(prompt)

        if updated_prompt is None:
            raise AppError(
                code="PROMPT_NOT_FOUND",
                message="This scene prompt could not be found.",
                http_status=404,
            )

        self.save_prompts(
            project_id, prompt_list.model_copy(update={"prompts": updated_prompts})
        )
        return updated_prompt

    # Explicit aliases keep persistence call sites readable.
    load_prompt_list = get_prompts
    save_prompt_list = save_prompts

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

    def _require_scenes(self, project_id: str) -> SceneList:
        scenes_file = metadata_path(self.projects_root, project_id, "scenes.json")
        if not scenes_file.is_file():
            raise AppError(
                code="SCENE_LIST_NOT_FOUND",
                message="No scene list exists yet. Split and approve the story first.",
                http_status=404,
            )
        try:
            return read_json_model(scenes_file, SceneList)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="SCENE_JSON_INVALID",
                message="The saved scene list is invalid. Split the story again.",
                http_status=422,
            ) from exc

    def _prompts_path(self, project_id: str) -> Path:
        return metadata_path(self.projects_root, project_id, "prompts.json")
