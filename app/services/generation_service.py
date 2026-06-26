import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.core.file_io import read_json_model, sha256_text, write_json
from app.core.paths import (
    metadata_path,
    output_images_dir,
    project_relative_path,
    project_root,
)
from app.schemas.character import CharacterMetadata, CharacterStatus
from app.schemas.generation import GenerationSettings
from app.schemas.jobs import GenerationJobStatus, SceneResultStatus
from app.schemas.manifest import (
    OutputAsset,
    OutputAssetStatus,
    OutputCharacterReference,
)
from app.schemas.project import ProjectMetadata
from app.schemas.project import ProjectStatus
from app.schemas.prompt import PromptList
from app.schemas.scene import Scene, SceneList
from app.services.character_service import CharacterService
from app.services.manifest_service import ManifestService
from app.services.prompt_service import PromptService
from app.services.scene_service import SceneService


class GenerationService:
    """Read generation prerequisites from local project metadata."""

    def __init__(self, projects_root: str | Path) -> None:
        self.projects_root = Path(projects_root)

    def get_project(self, project_id: str) -> ProjectMetadata:
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

    def get_generation_settings(self, project_id: str) -> GenerationSettings:
        settings_file = metadata_path(
            self.projects_root, project_id, "generation_settings.json"
        )
        if not settings_file.is_file():
            raise AppError(
                code="MODEL_CONFIG_INVALID",
                message="Generation model settings are missing. Recreate the project settings.",
                http_status=500,
            )
        try:
            settings = read_json_model(settings_file, GenerationSettings)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="MODEL_CONFIG_INVALID",
                message="Generation model settings are invalid. Check your local configuration.",
                http_status=500,
            ) from exc

        if (
            not settings.image_model.image_model_id.strip()
            or not settings.image_model.low_vram_image_model_id.strip()
        ):
            raise AppError(
                code="MODEL_CONFIG_INVALID",
                message="Generation model IDs must be configured before image generation.",
                http_status=500,
            )
        return settings

    def get_scene_list(self, project_id: str) -> SceneList:
        scene_list = SceneService(self.projects_root).get_scenes(project_id)
        if scene_list is None:
            raise AppError(
                code="SCENE_LIST_NOT_FOUND",
                message="No scene list exists yet. Split and approve the story first.",
                http_status=404,
            )
        return scene_list

    def require_ready_prompts(self, project_id: str) -> PromptList:
        return PromptService(self.projects_root).require_ready_prompts(project_id)

    def get_characters(self, project_id: str) -> CharacterMetadata | None:
        return CharacterService(self.projects_root).get_characters(project_id)

    def missing_character_references(
        self,
        project_id: str,
        active_scenes: list[Scene],
        prompt_list: PromptList | None,
    ) -> list[str]:
        required_names = {
            name.strip()
            for scene in active_scenes
            for name in scene.characters
            if name.strip()
        }
        if prompt_list is not None:
            required_names.update(
                character.name.strip()
                for prompt in prompt_list.prompts
                for character in prompt.characters
                if character.name.strip()
            )
        if not required_names:
            return []

        metadata = self.get_characters(project_id)
        references = metadata.characters if metadata is not None else []
        available_names = {
            reference.name.casefold()
            for reference in references
            if reference.status in {CharacterStatus.VALID, CharacterStatus.WARNING}
            and self._project_file_exists(project_id, reference.stored_path)
        }
        return sorted(
            name for name in required_names if name.casefold() not in available_names
        )

    def output_folder_is_writable(self, project_id: str) -> bool:
        output_dir = output_images_dir(self.projects_root, project_id)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output_dir,
                prefix=".readiness.",
                suffix=".tmp",
                delete=True,
            ) as temporary_file:
                temporary_file.write("ok")
                temporary_file.flush()
        except OSError:
            return False
        return True

    def generate_mock_images(self, project_id: str, job_id: str) -> None:
        from app.services.generation_job_service import GenerationJobService

        job_service = GenerationJobService(self.projects_root)
        job = job_service.get_status(project_id)
        if job is None or job.job_id != job_id:
            raise AppError(
                code="GENERATION_STATUS_NOT_FOUND",
                message="The generation job could not be found.",
                http_status=404,
            )

        scenes = self.get_scene_list(project_id).active_scenes
        prompt_list = self.require_ready_prompts(project_id)
        prompt_by_scene_id = {prompt.scene_id: prompt for prompt in prompt_list.prompts}
        manifest_service = ManifestService(self.projects_root)
        manifest = manifest_service.load_or_create(project_id, job_id)
        self._update_project_status(project_id, ProjectStatus.GENERATION_RUNNING)

        for scene in scenes:
            prompt = prompt_by_scene_id[scene.scene_id]
            job_service.mark_running(
                project_id,
                scene_id=scene.scene_id,
                scene_number=scene.scene_number,
                scene_title=scene.title,
            )
            try:
                filename = manifest_service.next_output_filename(
                    project_id,
                    scene_number=scene.scene_number,
                    title=scene.title or scene.summary,
                )
                relative_path = manifest_service.output_relative_path(
                    project_id, filename
                )
                absolute_path = (
                    project_root(self.projects_root, project_id) / relative_path
                )
                self._write_placeholder_png(
                    absolute_path,
                    width=prompt.generation_settings.width,
                    height=prompt.generation_settings.height,
                    scene=scene,
                )
                asset = OutputAsset(
                    asset_id=f"asset_{scene.scene_id}_{job_id}",
                    job_id=job_id,
                    scene_id=scene.scene_id,
                    scene_number=scene.scene_number,
                    scene_title=scene.title,
                    prompt_id=scene.scene_id,
                    output_filename=filename,
                    output_path=relative_path,
                    width=prompt.generation_settings.width,
                    height=prompt.generation_settings.height,
                    status=OutputAssetStatus.SUCCESS,
                    image_model_id=job.generation_plan.model_id,
                    pipeline=job.generation_plan.pipeline,
                    seed=prompt.generation_settings.seed or scene.scene_number,
                    num_inference_steps=prompt.generation_settings.num_inference_steps,
                    guidance_scale=prompt.generation_settings.guidance_scale,
                    output_preset_id=job.generation_plan.output_preset_id,
                    character_references=[
                        OutputCharacterReference(
                            name=character.name,
                            reference_image_path=character.reference_image_path,
                            runtime_consistency_mode=job.character_consistency.mode,
                        )
                        for character in prompt.characters
                    ],
                    positive_prompt_hash=f"sha256:{sha256_text(prompt.positive_prompt)}",
                    negative_prompt_hash=f"sha256:{sha256_text(prompt.negative_prompt)}",
                    created_at=datetime.now(timezone.utc),
                )
                manifest = manifest_service.record_asset(project_id, manifest, asset)
                job_service.record_scene_result(
                    project_id,
                    scene_id=scene.scene_id,
                    scene_number=scene.scene_number,
                    status=SceneResultStatus.SUCCESS,
                    output_path=relative_path,
                )
            except Exception:
                asset = OutputAsset(
                    asset_id=f"asset_{scene.scene_id}_{job_id}",
                    job_id=job_id,
                    scene_id=scene.scene_id,
                    scene_number=scene.scene_number,
                    scene_title=scene.title,
                    prompt_id=scene.scene_id,
                    width=prompt.generation_settings.width,
                    height=prompt.generation_settings.height,
                    status=OutputAssetStatus.FAILED,
                    image_model_id=job.generation_plan.model_id,
                    pipeline=job.generation_plan.pipeline,
                    seed=prompt.generation_settings.seed or scene.scene_number,
                    num_inference_steps=prompt.generation_settings.num_inference_steps,
                    guidance_scale=prompt.generation_settings.guidance_scale,
                    output_preset_id=job.generation_plan.output_preset_id,
                    character_references=[
                        OutputCharacterReference(
                            name=character.name,
                            reference_image_path=character.reference_image_path,
                            runtime_consistency_mode=job.character_consistency.mode,
                        )
                        for character in prompt.characters
                    ],
                    positive_prompt_hash=f"sha256:{sha256_text(prompt.positive_prompt)}",
                    negative_prompt_hash=f"sha256:{sha256_text(prompt.negative_prompt)}",
                    created_at=datetime.now(timezone.utc),
                    error_code="MOCK_GENERATION_FAILED",
                    error_message="The mock image could not be written.",
                )
                manifest = manifest_service.record_asset(project_id, manifest, asset)
                job_service.record_scene_result(
                    project_id,
                    scene_id=scene.scene_id,
                    scene_number=scene.scene_number,
                    status=SceneResultStatus.FAILED,
                    error_code="MOCK_GENERATION_FAILED",
                    error_message="The mock image could not be written.",
                )

        completed_job = job_service.get_status(project_id)
        if completed_job is None:
            raise AppError(
                code="GENERATION_STATUS_NOT_FOUND",
                message="The generation job status could not be finalized.",
                http_status=404,
            )
        if completed_job.failed_scenes == 0 and completed_job.completed_scenes:
            final_status = GenerationJobStatus.COMPLETED
            project_status = ProjectStatus.GENERATION_COMPLETED
        elif completed_job.completed_scenes:
            final_status = GenerationJobStatus.PARTIAL
            project_status = ProjectStatus.GENERATION_PARTIAL
        else:
            final_status = GenerationJobStatus.FAILED
            project_status = ProjectStatus.GENERATION_FAILED
        job_service.finalize_job(project_id, final_status)
        self._update_project_status(project_id, project_status)

    def _project_file_exists(self, project_id: str, relative_path: str) -> bool:
        try:
            safe_relative_path = project_relative_path(
                self.projects_root, project_id, relative_path
            )
        except ValueError:
            return False
        return (
            project_root(self.projects_root, project_id) / safe_relative_path
        ).is_file()

    def _update_project_status(self, project_id: str, status: ProjectStatus) -> None:
        project_file = metadata_path(self.projects_root, project_id, "project.json")
        project = read_json_model(project_file, ProjectMetadata)
        project.status = status
        project.updated_at = datetime.now(timezone.utc)
        write_json(project_file, project)

    @staticmethod
    def _write_placeholder_png(
        path: Path, *, width: int, height: int, scene: Scene
    ) -> None:
        from PIL import Image, ImageDraw

        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (width, height), color=(28, 30, 36))
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            (24, 24, max(25, width - 24), max(25, height - 24)),
            outline=(230, 184, 86),
            width=4,
        )
        draw.text(
            (48, 48), f"{scene.scene_number:03d} {scene.title}", fill=(245, 245, 245)
        )
        draw.text((48, 86), "Mock anime storyboard frame", fill=(180, 190, 205))
        draw.text((48, 124), scene.summary[:140], fill=(220, 220, 220))
        image.save(path, format="PNG")
