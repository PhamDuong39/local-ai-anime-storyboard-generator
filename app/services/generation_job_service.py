from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.core.errors import AppError
from app.core.file_io import read_json_model, write_json
from app.core.paths import metadata_path
from app.schemas.generation import (
    GenerationSettings,
    GenerationReadinessIssue,
    GenerationReadinessResult,
    HardwareDetection,
    HardwareProfile,
)
from app.schemas.jobs import (
    GenerationJob,
    GenerationJobStatus,
    SceneGenerationResult,
    SceneResultStatus,
)
from app.schemas.prompt import PromptList
from app.schemas.scene import Scene, SceneStatus
from app.services.generation_plan_service import (
    GenerationPlanSelection,
    GenerationPlanService,
)
from app.services.generation_service import GenerationService
from app.services.hardware_service import HardwareService


ACTIVE_JOB_STATUSES = {
    GenerationJobStatus.QUEUED,
    GenerationJobStatus.RUNNING,
    GenerationJobStatus.CANCEL_REQUESTED,
}
_JOB_START_LOCK = Lock()


class GenerationJobService:
    """Validate generation readiness before a local image job can start."""

    def __init__(
        self,
        projects_root: str | Path,
        *,
        hardware_service: HardwareService | None = None,
        is_job_running: Callable[[], bool] | None = None,
        output_writable_checker: Callable[[str], bool] | None = None,
    ) -> None:
        self.projects_root = Path(projects_root)
        self.hardware_service = hardware_service or HardwareService()
        self.generation_service = GenerationService(self.projects_root)
        self._is_job_running = is_job_running or (lambda: False)
        self._output_writable_checker = output_writable_checker

    def check_readiness(
        self, project_id: str, *, confirm_cpu_slow: bool = False
    ) -> GenerationReadinessResult:
        blocking_errors: list[GenerationReadinessIssue] = []
        warnings: list[GenerationReadinessIssue] = []
        active_scenes: list[Scene] = []
        prompt_list: PromptList | None = None
        hardware = self.hardware_service.detect_hardware()

        if self._has_active_job(project_id):
            blocking_errors.append(
                self._issue(
                    "GENERATION_ALREADY_RUNNING",
                    "Generation is already running. Please wait before starting another job.",
                )
            )

        try:
            self.generation_service.get_project(project_id)
        except AppError:
            blocking_errors.append(
                self._issue("PROJECT_NOT_FOUND", "This project could not be found.")
            )
            return self._result(project_id, hardware, warnings, blocking_errors)

        try:
            self.generation_service.get_generation_settings(project_id)
        except AppError as exc:
            blocking_errors.append(self._issue(exc.code, exc.message, exc.details))

        try:
            scene_list = self.generation_service.get_scene_list(project_id)
            active_scenes = scene_list.active_scenes
            if not active_scenes or any(
                scene.status is not SceneStatus.APPROVED for scene in active_scenes
            ):
                blocking_errors.append(
                    self._issue(
                        "SCENE_APPROVAL_REQUIRED",
                        "Review and approve every active scene before image generation.",
                    )
                )
        except AppError as exc:
            blocking_errors.append(self._issue(exc.code, exc.message, exc.details))

        try:
            prompt_list = self.generation_service.require_ready_prompts(project_id)
        except AppError as exc:
            blocking_errors.append(self._issue(exc.code, exc.message, exc.details))

        if active_scenes:
            missing_names = self.generation_service.missing_character_references(
                project_id, active_scenes, prompt_list
            )
            if missing_names:
                blocking_errors.append(
                    self._issue(
                        "CHARACTER_REFERENCE_MISSING",
                        "Upload one reference image for each character before generation.",
                        {"character_names": missing_names},
                    )
                )

        if not self._output_folder_is_writable(project_id):
            blocking_errors.append(
                self._issue(
                    "OUTPUT_FOLDER_NOT_WRITABLE",
                    "The output image folder is not writable. Check folder permissions and try again.",
                )
            )

        self._add_hardware_warnings(
            hardware,
            warnings=warnings,
            blocking_errors=blocking_errors,
            confirm_cpu_slow=confirm_cpu_slow,
        )

        return self._result(
            project_id,
            hardware,
            warnings,
            blocking_errors,
            active_scene_count=len(active_scenes),
            prompt_count=len(prompt_list.prompts) if prompt_list is not None else 0,
        )

    def start_job(
        self, project_id: str, *, confirm_cpu_slow: bool = False
    ) -> GenerationJob:
        with _JOB_START_LOCK:
            readiness = self.check_readiness(
                project_id, confirm_cpu_slow=confirm_cpu_slow
            )
            if not readiness.ok:
                first_error = readiness.blocking_errors[0]
                raise AppError(
                    code=first_error.code,
                    message=first_error.message,
                    http_status=self._http_status_for_code(first_error.code),
                    details={
                        **first_error.details,
                        "blocking_error_codes": [
                            error.code for error in readiness.blocking_errors
                        ],
                        "warning_codes": [
                            warning.code for warning in readiness.warnings
                        ],
                    },
                )
            return self.create_queued_job(project_id, readiness)

    def create_queued_job(
        self, project_id: str, readiness: GenerationReadinessResult
    ) -> GenerationJob:
        settings = self.generation_service.get_generation_settings(project_id)
        now = datetime.now(timezone.utc)
        selection = self._select_generation_plan(
            settings=settings,
            hardware=readiness.hardware,
        )
        job = GenerationJob(
            project_id=project_id,
            job_id=f"gen_{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
            status=GenerationJobStatus.QUEUED,
            started_at=now,
            updated_at=now,
            generation_plan=selection.generation_plan,
            character_consistency=selection.character_consistency,
            total_scenes=readiness.active_scene_count,
            current_message="Generation job queued.",
        )
        self.save_status(project_id, job)
        return job

    def get_status(self, project_id: str) -> GenerationJob | None:
        status_file = self._status_path(project_id)
        if not status_file.is_file():
            return None
        try:
            return read_json_model(status_file, GenerationJob)
        except (OSError, ValueError) as exc:
            raise AppError(
                code="GENERATION_STATUS_INVALID",
                message="The saved generation status could not be read.",
                http_status=500,
            ) from exc

    def save_status(self, project_id: str, job: GenerationJob) -> GenerationJob:
        if job.project_id != project_id:
            raise AppError(
                code="GENERATION_STATUS_PROJECT_MISMATCH",
                message="Generation status does not belong to this project.",
                http_status=400,
            )
        validated = GenerationJob.model_validate(job.model_dump(mode="json"))
        write_json(self._status_path(project_id), validated)
        return validated

    def mark_running(
        self,
        project_id: str,
        *,
        scene_id: str,
        scene_number: int,
        scene_title: str,
    ) -> GenerationJob:
        job = self._require_status(project_id)
        updated = job.model_copy(
            update={
                "status": GenerationJobStatus.RUNNING,
                "updated_at": datetime.now(timezone.utc),
                "current_scene_id": scene_id,
                "current_scene_number": scene_number,
                "current_scene_title": scene_title,
                "current_message": (
                    f"Generating scene {scene_number} of {job.total_scenes}"
                ),
            }
        )
        return self.save_status(project_id, updated)

    def record_scene_result(
        self,
        project_id: str,
        *,
        scene_id: str,
        scene_number: int,
        status: SceneResultStatus,
        output_path: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> GenerationJob:
        job = self._require_status(project_id)
        now = datetime.now(timezone.utc)
        existing_results = [
            result for result in job.scene_results if result.scene_id != scene_id
        ]
        result = SceneGenerationResult(
            scene_id=scene_id,
            scene_number=scene_number,
            status=status,
            output_path=output_path,
            error_code=error_code,
            error_message=error_message,
            started_at=now,
            completed_at=now,
        )
        scene_results = [*existing_results, result]
        completed_scenes = sum(
            item.status is SceneResultStatus.SUCCESS for item in scene_results
        )
        failed_scenes = sum(
            item.status is SceneResultStatus.FAILED for item in scene_results
        )
        skipped_scenes = sum(
            item.status is SceneResultStatus.SKIPPED for item in scene_results
        )
        finished_scenes = completed_scenes + failed_scenes + skipped_scenes
        progress_percent = (
            int(finished_scenes / job.total_scenes * 100) if job.total_scenes else 0
        )
        updated = job.model_copy(
            update={
                "updated_at": now,
                "completed_scenes": completed_scenes,
                "failed_scenes": failed_scenes,
                "skipped_scenes": skipped_scenes,
                "progress_percent": progress_percent,
                "scene_results": sorted(
                    scene_results, key=lambda item: item.scene_number
                ),
                "current_message": (
                    f"Finished {finished_scenes} of {job.total_scenes} scenes"
                ),
            }
        )
        return self.save_status(project_id, updated)

    def finalize_job(
        self,
        project_id: str,
        status: GenerationJobStatus,
        *,
        errors: list[str] | None = None,
    ) -> GenerationJob:
        if status not in {
            GenerationJobStatus.COMPLETED,
            GenerationJobStatus.PARTIAL,
            GenerationJobStatus.FAILED,
            GenerationJobStatus.CANCELLED,
        }:
            raise AppError(
                code="GENERATION_STATUS_INVALID",
                message="Generation can only be finalized with a terminal status.",
                http_status=400,
            )
        job = self._require_status(project_id)
        now = datetime.now(timezone.utc)
        progress_percent = (
            100 if status is GenerationJobStatus.COMPLETED else job.progress_percent
        )
        updated = job.model_copy(
            update={
                "status": status,
                "updated_at": now,
                "completed_at": now,
                "progress_percent": progress_percent,
                "current_message": f"Generation {status.value}.",
                "errors": errors if errors is not None else job.errors,
            }
        )
        return self.save_status(project_id, updated)

    def _output_folder_is_writable(self, project_id: str) -> bool:
        if self._output_writable_checker is not None:
            return self._output_writable_checker(project_id)
        return self.generation_service.output_folder_is_writable(project_id)

    def _has_active_job(self, project_id: str) -> bool:
        if self._is_job_running():
            return True
        existing = self.get_status(project_id)
        return existing is not None and existing.status in ACTIVE_JOB_STATUSES

    def _require_status(self, project_id: str) -> GenerationJob:
        job = self.get_status(project_id)
        if job is None:
            raise AppError(
                code="GENERATION_STATUS_NOT_FOUND",
                message="No generation job status exists for this project.",
                http_status=404,
            )
        return job

    def _status_path(self, project_id: str) -> Path:
        return metadata_path(self.projects_root, project_id, "generation_status.json")

    @staticmethod
    def _select_generation_plan(
        *,
        settings: GenerationSettings,
        hardware: HardwareDetection | None,
    ) -> GenerationPlanSelection:
        return GenerationPlanService().select(settings=settings, hardware=hardware)

    @staticmethod
    def _add_hardware_warnings(
        hardware: HardwareDetection,
        *,
        warnings: list[GenerationReadinessIssue],
        blocking_errors: list[GenerationReadinessIssue],
        confirm_cpu_slow: bool,
    ) -> None:
        if hardware.hardware_profile is HardwareProfile.CPU_ONLY:
            issue = GenerationJobService._issue(
                "CPU_GENERATION_SLOW",
                "CPU image generation is available but will be very slow.",
            )
            warnings.append(issue)
            if not confirm_cpu_slow:
                blocking_errors.append(
                    GenerationJobService._issue(
                        "CPU_GENERATION_CONFIRMATION_REQUIRED",
                        "Confirm that CPU generation may be very slow before starting.",
                    )
                )
        elif hardware.hardware_profile is HardwareProfile.LOW_VRAM_4GB:
            warnings.append(
                GenerationJobService._issue(
                    "LOW_VRAM_MODE_RECOMMENDED",
                    "Your GPU has limited VRAM. Low VRAM Preview is recommended.",
                    {"vram_gb": hardware.vram_gb},
                )
            )
        elif hardware.hardware_profile is HardwareProfile.MID_VRAM_6_8GB:
            warnings.append(
                GenerationJobService._issue(
                    "MID_VRAM_CAUTION",
                    "Your GPU may need cautious image settings. Quality mode can be slower or fail on larger presets.",
                    {"vram_gb": hardware.vram_gb},
                )
            )
        elif hardware.hardware_profile is HardwareProfile.UNKNOWN:
            warnings.append(
                GenerationJobService._issue(
                    "HARDWARE_DETECTION_UNKNOWN",
                    "Hardware detection did not complete. The app will use the safest available generation path.",
                )
            )

    @staticmethod
    def _result(
        project_id: str,
        hardware: HardwareDetection,
        warnings: list[GenerationReadinessIssue],
        blocking_errors: list[GenerationReadinessIssue],
        *,
        active_scene_count: int = 0,
        prompt_count: int = 0,
    ) -> GenerationReadinessResult:
        return GenerationReadinessResult(
            ok=not blocking_errors,
            project_id=project_id,
            active_scene_count=active_scene_count,
            prompt_count=prompt_count,
            hardware=hardware,
            warnings=warnings,
            blocking_errors=blocking_errors,
        )

    @staticmethod
    def _issue(
        code: str, message: str, details: dict[str, object] | None = None
    ) -> GenerationReadinessIssue:
        return GenerationReadinessIssue(
            code=code,
            message=message,
            details=details or {},
        )

    @staticmethod
    def _http_status_for_code(code: str) -> int:
        if code == "PROJECT_NOT_FOUND":
            return 404
        if code in {"MODEL_CONFIG_INVALID", "OUTPUT_FOLDER_NOT_WRITABLE"}:
            return 500
        if code in {
            "GENERATION_ALREADY_RUNNING",
            "SCENE_APPROVAL_REQUIRED",
            "PROMPTS_MISSING",
            "PROMPT_STALE",
            "CHARACTER_REFERENCE_MISSING",
            "CPU_GENERATION_CONFIRMATION_REQUIRED",
        }:
            return 409
        return 422
