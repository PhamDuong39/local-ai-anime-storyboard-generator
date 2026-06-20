from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from app.core.errors import AppError
from app.core.file_io import read_json_model, write_json
from app.core.paths import metadata_path
from app.schemas.project import ProjectMetadata, ProjectStatus
from app.schemas.prompt import PromptList, PromptStatus
from app.schemas.scene import Scene, SceneList, SceneStatus


class SceneService:
    """Manage validated scene metadata without depending on an AI provider."""

    def __init__(self, projects_root: str | Path) -> None:
        self.projects_root = Path(projects_root)

    def save_scenes(self, project_id: str, scene_list: SceneList) -> SceneList:
        self._require_project(project_id)
        if scene_list.project_id != project_id:
            raise AppError(
                code="SCENE_PROJECT_MISMATCH",
                message="The scene list does not belong to this project.",
                http_status=400,
            )

        # Revalidate at the storage boundary in case a caller constructed a model
        # without validation or mutated nested values after construction.
        try:
            validated = SceneList.model_validate(scene_list.model_dump(mode="json"))
            write_json(self._scenes_path(project_id), validated)
        except ValidationError as exc:
            raise AppError(
                code="SCENE_JSON_INVALID",
                message="The scene list is invalid. Review the scene order and try again.",
                http_status=422,
            ) from exc
        except OSError as exc:
            raise AppError(
                code="SCENE_SAVE_FAILED",
                message="The scene list could not be saved locally. Please try again.",
                http_status=500,
            ) from exc
        return validated

    def get_scenes(self, project_id: str) -> SceneList | None:
        self._require_project(project_id)
        scenes_file = self._scenes_path(project_id)
        if not scenes_file.is_file():
            return None
        try:
            return read_json_model(scenes_file, SceneList)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="SCENE_READ_FAILED",
                message="The saved scene list could not be read. Split the story again.",
                http_status=500,
            ) from exc

    def reorder_scenes(
        self, project_id: str, ordered_scene_ids: Sequence[str]
    ) -> SceneList:
        scene_list = self._require_scenes(project_id)
        current_ids = [scene.scene_id for scene in scene_list.scenes]
        requested_ids = list(ordered_scene_ids)
        if len(requested_ids) != len(set(requested_ids)) or set(requested_ids) != set(
            current_ids
        ):
            raise AppError(
                code="SCENE_REORDER_INVALID",
                message="The new scene order must include every scene exactly once.",
                http_status=422,
            )

        scenes_by_id = {scene.scene_id: scene for scene in scene_list.scenes}
        reordered = [scenes_by_id[scene_id] for scene_id in requested_ids]
        updated = scene_list.model_copy(
            update={"scenes": self._renumber_active_scenes(reordered)}
        )
        saved = self.save_scenes(project_id, updated)
        self._mark_prompts_stale(project_id)
        return saved

    def update_scene(
        self, project_id: str, scene_id: str, updates: dict[str, object]
    ) -> Scene:
        scene_list = self._require_scenes(project_id)
        updated_scenes: list[Scene] = []
        updated_scene: Scene | None = None
        for scene in scene_list.scenes:
            if scene.scene_id == scene_id:
                try:
                    updated_scene = Scene.model_validate(
                        {
                            **scene.model_dump(mode="json"),
                            **updates,
                            "scene_id": scene.scene_id,
                            "scene_number": scene.scene_number,
                            "status": SceneStatus.NEEDS_EDIT,
                        }
                    )
                except ValidationError as exc:
                    raise AppError(
                        code="SCENE_UPDATE_INVALID",
                        message=(
                            "This scene could not be saved. Complete the required "
                            "fields and include 3 to 8 visual details."
                        ),
                        http_status=400,
                    ) from exc
                scene = updated_scene
            updated_scenes.append(scene)
        if updated_scene is None:
            raise AppError(
                code="SCENE_NOT_FOUND",
                message="This scene could not be found.",
                http_status=404,
            )

        self.save_scenes(
            project_id, scene_list.model_copy(update={"scenes": updated_scenes})
        )
        self._mark_prompts_stale(project_id, scene_id=scene_id)
        return updated_scene

    def skip_scene(self, project_id: str, scene_id: str) -> SceneList:
        scene_list = self._require_scenes(project_id)
        target = next(
            (scene for scene in scene_list.scenes if scene.scene_id == scene_id), None
        )
        if target is None:
            raise AppError(
                code="SCENE_NOT_FOUND",
                message="This scene could not be found.",
                http_status=404,
            )
        if (
            target.status is not SceneStatus.SKIPPED
            and len(scene_list.active_scenes) == 1
        ):
            raise AppError(
                code="SCENE_SKIP_INVALID",
                message="Keep at least one active scene before continuing.",
                http_status=400,
            )

        found = False
        updated_scenes: list[Scene] = []
        for scene in scene_list.scenes:
            if scene.scene_id == scene_id:
                scene = scene.model_copy(update={"status": SceneStatus.SKIPPED})
                found = True
            updated_scenes.append(scene)
        if not found:
            raise AppError(
                code="SCENE_NOT_FOUND",
                message="This scene could not be found.",
                http_status=404,
            )

        updated = scene_list.model_copy(
            update={"scenes": self._renumber_active_scenes(updated_scenes)}
        )
        saved = self.save_scenes(project_id, updated)
        self._mark_prompts_stale(project_id, scene_id=scene_id)
        return saved

    def approve_scenes(self, project_id: str) -> SceneList:
        scene_list = self._require_scenes(project_id)
        if not scene_list.active_scenes:
            raise AppError(
                code="SCENE_APPROVAL_REQUIRED",
                message="Keep at least one active scene before approving the list.",
                http_status=400,
            )
        approved = scene_list.model_copy(
            update={
                "scenes": [
                    scene
                    if scene.status is SceneStatus.SKIPPED
                    else scene.model_copy(update={"status": SceneStatus.APPROVED})
                    for scene in scene_list.scenes
                ]
            }
        )
        saved = self.save_scenes(project_id, approved)
        project_file = metadata_path(self.projects_root, project_id, "project.json")
        try:
            project = read_json_model(project_file, ProjectMetadata)
            project.status = ProjectStatus.SCENES_APPROVED
            project.updated_at = datetime.now(timezone.utc)
            write_json(project_file, project)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="SCENE_APPROVAL_FAILED",
                message="The scene list was saved, but approval could not be recorded.",
                http_status=500,
            ) from exc
        return saved

    def get_generation_scenes(self, project_id: str) -> list[Scene]:
        """Return ordered active scenes; skipped scenes never enter generation."""
        return list(self._require_scenes(project_id).active_scenes)

    # Explicit aliases make the persistence API readable at call sites.
    load_scene_list = get_scenes
    save_scene_list = save_scenes

    @staticmethod
    def _renumber_active_scenes(scenes: Sequence[Scene]) -> list[Scene]:
        next_number = 1
        renumbered: list[Scene] = []
        for scene in scenes:
            if scene.status is not SceneStatus.SKIPPED:
                scene = scene.model_copy(update={"scene_number": next_number})
                next_number += 1
            renumbered.append(scene)
        return renumbered

    def _require_scenes(self, project_id: str) -> SceneList:
        scene_list = self.get_scenes(project_id)
        if scene_list is None:
            raise AppError(
                code="SCENE_LIST_NOT_FOUND",
                message="No scene list exists yet. Split the story into scenes first.",
                http_status=404,
            )
        return scene_list

    def _require_project(self, project_id: str) -> None:
        if not metadata_path(self.projects_root, project_id, "project.json").is_file():
            raise AppError(
                code="PROJECT_NOT_FOUND",
                message="This project could not be found.",
                http_status=404,
            )

    def _scenes_path(self, project_id: str) -> Path:
        return metadata_path(self.projects_root, project_id, "scenes.json")

    def _mark_prompts_stale(
        self, project_id: str, *, scene_id: str | None = None
    ) -> None:
        prompts_file = metadata_path(self.projects_root, project_id, "prompts.json")
        if not prompts_file.is_file():
            return
        try:
            prompts = read_json_model(prompts_file, PromptList)
            for prompt in prompts.prompts:
                if scene_id is None or prompt.scene_id == scene_id:
                    prompt.status = PromptStatus.STALE
            write_json(prompts_file, prompts)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="PROMPT_STALE_UPDATE_FAILED",
                message="The scene changed, but existing prompts could not be marked stale.",
                http_status=500,
            ) from exc
