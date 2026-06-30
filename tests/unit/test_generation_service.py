from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from PIL import Image

from app.core.file_io import read_json, write_json
from app.core.paths import metadata_path, project_root
from app.schemas.character import CharacterMetadata
from app.schemas.generation import HardwareDetection, HardwareProfile
from app.schemas.jobs import GenerationJobStatus
from app.schemas.prompt import PromptList
from app.schemas.project import ProjectStatus
from app.schemas.scene import SceneList
from app.services import generation_service as generation_service_module
from app.services.generation_job_service import GenerationJobService
from app.services.generation_service import GenerationService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.scene_service import SceneService


NOW = datetime(2026, 6, 11, 10, 15, 30, tzinfo=timezone.utc)


class FakeHardwareService:
    def __init__(self, profile: HardwareProfile = HardwareProfile.HIGH_VRAM_12GB_PLUS):
        self.profile = profile

    def detect_hardware(self) -> HardwareDetection:
        if self.profile is HardwareProfile.LOW_VRAM_4GB:
            return HardwareDetection(
                device="cuda",
                gpu_name="Low VRAM GPU",
                vram_gb=4,
                cuda_available=True,
                hardware_profile=HardwareProfile.LOW_VRAM_4GB,
                detected_at=NOW,
            )
        return HardwareDetection(
            device="cuda",
            gpu_name="High VRAM GPU",
            vram_gb=12,
            cuda_available=True,
            hardware_profile=HardwareProfile.HIGH_VRAM_12GB_PLUS,
            detected_at=NOW,
        )


class FakeGenerator:
    def __init__(self, device: str) -> None:
        self.device = device
        self.seed: int | None = None

    def manual_seed(self, seed: int) -> "FakeGenerator":
        self.seed = seed
        return self


class FakeCuda:
    class OutOfMemoryError(RuntimeError):
        pass

    def __init__(self) -> None:
        self.empty_cache_calls = 0

    def empty_cache(self) -> None:
        self.empty_cache_calls += 1


class FakePipelineResult:
    def __init__(self, images: list[object]) -> None:
        self.images = images


class FakePipeline:
    def __init__(self, effects: list[object] | None = None) -> None:
        self.effects = effects or [Image.new("RGB", (8, 8), color=(180, 180, 180))]
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> FakePipelineResult:
        self.calls.append(kwargs)
        effect = self.effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        if isinstance(effect, FakePipelineResult):
            return effect
        if callable(effect):
            effect()
            image = Image.new("RGB", (8, 8), color=(120, 120, 120))
            return FakePipelineResult([image])
        return FakePipelineResult([effect])


class FakePipelineFactory:
    def __init__(
        self,
        pipeline: FakePipeline | None = None,
        load_error: Exception | None = None,
    ) -> None:
        self.pipeline = pipeline or FakePipeline()
        self.load_error = load_error
        self.load_calls: list[object] = []
        self.unload_calls = 0

    def load(self, plan: object) -> FakePipeline:
        self.load_calls.append(plan)
        if self.load_error is not None:
            raise self.load_error
        return self.pipeline

    def unload(self) -> None:
        self.unload_calls += 1


def install_fake_torch(monkeypatch) -> FakeCuda:
    fake_cuda = FakeCuda()
    fake_torch = SimpleNamespace(
        Generator=FakeGenerator,
        cuda=fake_cuda,
    )

    def fake_import_module(name: str):
        if name == "torch":
            return fake_torch
        raise ImportError(name)

    monkeypatch.setattr(generation_service_module, "import_module", fake_import_module)
    return fake_cuda


def scene(scene_number: int = 1) -> dict[str, object]:
    return {
        "scene_id": f"scene_{scene_number:03d}",
        "scene_number": scene_number,
        "title": "School gate" if scene_number == 1 else f"School gate {scene_number}",
        "source_excerpt": "Akira enters the school.",
        "summary": "Akira enters the empty school.",
        "characters": ["Akira"],
        "location": "school gate",
        "time_of_day": "dusk",
        "mood": "tense",
        "main_action": "Akira enters the gate",
        "camera_shot": "wide shot",
        "camera_angle": "eye level",
        "visual_details": ["rusted gate", "orange sky", "empty yard"],
        "continuity_notes": [],
        "status": "approved",
    }


def prompt(scene_number: int = 1, seed: int | None = None) -> dict[str, object]:
    data = {
        "scene_id": f"scene_{scene_number:03d}",
        "scene_number": scene_number,
        "positive_prompt": "anime storyboard illustration",
        "negative_prompt": "text, subtitle, watermark, logo",
        "characters": [
            {
                "name": "Akira",
                "reference_image_path": "input/characters/Akira.png",
                "consistency_method": "ip-adapter-faceid",
                "role_in_scene": "main character",
                "visual_priority": "high",
            }
        ],
        "generation_settings": {"width": 1280, "height": 720},
        "status": "ready",
    }
    if seed is not None:
        data["generation_settings"]["seed"] = seed
    return data


def make_ready_project(
    tmp_path,
    *,
    scene_count: int = 1,
    profile: HardwareProfile = HardwareProfile.HIGH_VRAM_12GB_PLUS,
    continue_on_scene_failure: bool = True,
):
    root = tmp_path / "projects"
    project = ProjectService(
        root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("Mock Generation", "youtube_standard")
    SceneService(root).save_scenes(
        project.project_id,
        SceneList.model_validate(
            {
                "project_id": project.project_id,
                "scene_count": scene_count,
                "scenes": [
                    scene(scene_number) for scene_number in range(1, scene_count + 1)
                ],
            }
        ),
    )
    character_path = (
        project_root(root, project.project_id) / "input/characters/Akira.png"
    )
    character_path.write_bytes(b"reference")
    write_json(
        metadata_path(root, project.project_id, "characters.json"),
        CharacterMetadata.model_validate(
            {
                "characters": [
                    {
                        "name": "Akira",
                        "original_filename": "Akira.png",
                        "stored_path": "input/characters/Akira.png",
                        "mime_type": "image/png",
                        "width": 1024,
                        "height": 1536,
                        "file_size_bytes": 9,
                        "consistency_method": "ip-adapter-faceid",
                        "status": "valid",
                    }
                ]
            }
        ),
    )
    PromptService(root).save_prompts(
        project.project_id,
        PromptList.model_validate(
            {
                "project_id": project.project_id,
                "output_preset": project.output_preset.model_dump(mode="json"),
                "prompts": [
                    prompt(scene_number) for scene_number in range(1, scene_count + 1)
                ],
            }
        ),
    )
    if not continue_on_scene_failure:
        settings_path = metadata_path(
            root, project.project_id, "generation_settings.json"
        )
        settings = read_json(settings_path)
        settings["safety"]["continue_on_scene_failure"] = False
        write_json(settings_path, settings)
    job_service = GenerationJobService(
        root, hardware_service=FakeHardwareService(profile)
    )
    job = job_service.start_job(project.project_id)
    return root, project, job, job_service


def make_mock_ready_project(tmp_path):
    root = tmp_path / "projects"
    project = ProjectService(
        root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("Mock Generation", "youtube_standard")
    SceneService(root).save_scenes(
        project.project_id,
        SceneList.model_validate(
            {
                "project_id": project.project_id,
                "scene_count": 1,
                "scenes": [scene()],
            }
        ),
    )
    character_path = (
        project_root(root, project.project_id) / "input/characters/Akira.png"
    )
    character_path.write_bytes(b"reference")
    write_json(
        metadata_path(root, project.project_id, "characters.json"),
        CharacterMetadata.model_validate(
            {
                "characters": [
                    {
                        "name": "Akira",
                        "original_filename": "Akira.png",
                        "stored_path": "input/characters/Akira.png",
                        "mime_type": "image/png",
                        "width": 1024,
                        "height": 1536,
                        "file_size_bytes": 9,
                        "consistency_method": "ip-adapter-faceid",
                        "status": "valid",
                    }
                ]
            }
        ),
    )
    PromptService(root).save_prompts(
        project.project_id,
        PromptList.model_validate(
            {
                "project_id": project.project_id,
                "output_preset": project.output_preset.model_dump(mode="json"),
                "prompts": [prompt()],
            }
        ),
    )
    return root, project


def test_mock_generation_writes_png_manifest_status_and_project_state(tmp_path) -> None:
    root, project = make_mock_ready_project(tmp_path)
    job_service = GenerationJobService(root, hardware_service=FakeHardwareService())
    job = job_service.start_job(project.project_id)

    GenerationService(root).generate_mock_images(project.project_id, job.job_id)

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    project_metadata = read_json(root / project.project_id / "metadata/project.json")
    image_path = root / project.project_id / manifest["assets"][0]["output_path"]

    assert status["status"] == "completed"
    assert status["completed_scenes"] == 1
    assert manifest["assets"][0]["scene_id"] == "scene_001"
    assert manifest["assets"][0]["output_filename"] == "001_school_gate.png"
    assert project_metadata["status"] == ProjectStatus.GENERATION_COMPLETED.value
    assert Image.open(image_path).size == (1280, 720)


def test_real_sd15_generation_writes_png_manifest_status_and_project_state(
    monkeypatch, tmp_path
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(
        tmp_path, profile=HardwareProfile.LOW_VRAM_4GB
    )
    pipeline = FakePipeline()

    GenerationService(root).generate_real_sd15_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    project_metadata = read_json(root / project.project_id / "metadata/project.json")
    image_path = root / project.project_id / manifest["assets"][0]["output_path"]

    assert status["status"] == "completed"
    assert status["scene_results"][0]["seed"] == 1234
    assert manifest["assets"][0]["pipeline"] == "sd15"
    assert manifest["assets"][0]["seed"] == 1234
    assert manifest["assets"][0]["positive_prompt_hash"].startswith("sha256:")
    assert project_metadata["status"] == ProjectStatus.GENERATION_COMPLETED.value
    assert Image.open(image_path).size == (8, 8)
    assert pipeline.calls[0]["prompt"] == "anime storyboard illustration"
    assert pipeline.calls[0]["negative_prompt"] == "text, subtitle, watermark, logo"
    assert pipeline.calls[0]["width"] == 1280
    assert pipeline.calls[0]["height"] == 720
    assert pipeline.calls[0]["num_inference_steps"] == 30
    assert pipeline.calls[0]["guidance_scale"] == 7.0
    assert pipeline.calls[0]["generator"].device == "cuda"
    assert pipeline.calls[0]["generator"].seed == 1234


def test_real_sdxl_generation_writes_png_manifest_status_and_project_state(
    monkeypatch, tmp_path
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(tmp_path)
    pipeline = FakePipeline()
    factory = FakePipelineFactory(pipeline)

    GenerationService(root).generate_real_images(
        project.project_id,
        job.job_id,
        pipeline_factory=factory,
        seed_factory=lambda: 1234,
    )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    image_path = root / project.project_id / manifest["assets"][0]["output_path"]

    assert factory.load_calls[0].pipeline.value == "sdxl"
    assert status["status"] == "completed"
    assert status["scene_results"][0]["seed"] == 1234
    assert manifest["assets"][0]["pipeline"] == "sdxl"
    assert manifest["assets"][0]["image_model_id"] == "sdxl-model"
    assert manifest["assets"][0]["seed"] == 1234
    assert manifest["assets"][0]["width"] == 1280
    assert manifest["assets"][0]["height"] == 720
    assert manifest["assets"][0]["num_inference_steps"] == 30
    assert manifest["assets"][0]["guidance_scale"] == 7.0
    assert (
        manifest["assets"][0]["character_references"][0]["runtime_consistency_mode"]
        == "faceid_unavailable"
    )
    assert Image.open(image_path).size == (8, 8)
    assert pipeline.calls[0]["prompt"] == "anime storyboard illustration"
    assert pipeline.calls[0]["negative_prompt"] == "text, subtitle, watermark, logo"
    assert pipeline.calls[0]["width"] == 1280
    assert pipeline.calls[0]["height"] == 720
    assert pipeline.calls[0]["num_inference_steps"] == 30
    assert pipeline.calls[0]["guidance_scale"] == 7.0
    assert pipeline.calls[0]["generator"].device == "cuda"
    assert pipeline.calls[0]["generator"].seed == 1234


def test_real_sd15_generation_uses_prompt_seed(monkeypatch, tmp_path) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(
        tmp_path, profile=HardwareProfile.LOW_VRAM_4GB
    )
    prompts_path = metadata_path(root, project.project_id, "prompts.json")
    prompts = read_json(prompts_path)
    prompts["prompts"][0]["generation_settings"]["seed"] = 777
    write_json(prompts_path, prompts)

    GenerationService(root).generate_real_sd15_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(),
        seed_factory=lambda: 1234,
    )

    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    status = read_json(root / project.project_id / "metadata/generation_status.json")
    assert manifest["assets"][0]["seed"] == 777
    assert status["scene_results"][0]["seed"] == 777


def test_real_sdxl_generation_uses_prompt_seed(monkeypatch, tmp_path) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(tmp_path)
    prompts_path = metadata_path(root, project.project_id, "prompts.json")
    prompts = read_json(prompts_path)
    prompts["prompts"][0]["generation_settings"]["seed"] = 777
    write_json(prompts_path, prompts)

    GenerationService(root).generate_real_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(),
        seed_factory=lambda: 1234,
    )

    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    status = read_json(root / project.project_id / "metadata/generation_status.json")
    assert manifest["assets"][0]["seed"] == 777
    assert status["scene_results"][0]["seed"] == 777


@pytest.mark.parametrize("images", [[], ["not an image"]])
def test_real_sd15_invalid_pipeline_result_records_scene_failure(
    monkeypatch, tmp_path, images
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(
        tmp_path, profile=HardwareProfile.LOW_VRAM_4GB
    )
    pipeline = FakePipeline(effects=[images[0] if images else FakePipelineResult([])])

    GenerationService(root).generate_real_sd15_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    status = read_json(root / project.project_id / "metadata/generation_status.json")
    assert status["status"] == "failed"
    assert status["scene_results"][0]["error_code"] == "SCENE_GENERATION_FAILED"
    assert manifest["assets"][0]["status"] == "failed"
    assert manifest["assets"][0]["error_code"] == "SCENE_GENERATION_FAILED"


@pytest.mark.parametrize("images", [[], ["not an image"]])
def test_real_sdxl_invalid_pipeline_result_records_scene_failure(
    monkeypatch, tmp_path, images
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(tmp_path)
    pipeline = FakePipeline(effects=[images[0] if images else FakePipelineResult([])])

    GenerationService(root).generate_real_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    status = read_json(root / project.project_id / "metadata/generation_status.json")
    assert status["status"] == "failed"
    assert status["scene_results"][0]["error_code"] == "SCENE_GENERATION_FAILED"
    assert manifest["assets"][0]["pipeline"] == "sdxl"
    assert manifest["assets"][0]["status"] == "failed"
    assert manifest["assets"][0]["error_code"] == "SCENE_GENERATION_FAILED"


def test_real_sd15_later_scene_failure_preserves_success_and_finalizes_partial(
    monkeypatch, tmp_path
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(
        tmp_path, scene_count=2, profile=HardwareProfile.LOW_VRAM_4GB
    )
    pipeline = FakePipeline(
        effects=[
            Image.new("RGB", (8, 8), color=(180, 180, 180)),
            RuntimeError("boom"),
        ]
    )

    GenerationService(root).generate_real_sd15_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    status = read_json(root / project.project_id / "metadata/generation_status.json")
    project_metadata = read_json(root / project.project_id / "metadata/project.json")
    assert status["status"] == "partial"
    assert status["completed_scenes"] == 1
    assert status["failed_scenes"] == 1
    assert manifest["assets"][0]["status"] == "success"
    assert (root / project.project_id / manifest["assets"][0]["output_path"]).is_file()
    assert manifest["assets"][1]["error_code"] == "SCENE_GENERATION_FAILED"
    assert project_metadata["status"] == ProjectStatus.GENERATION_PARTIAL.value


def test_real_sdxl_later_scene_failure_preserves_success_and_finalizes_partial(
    monkeypatch, tmp_path
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(tmp_path, scene_count=2)
    pipeline = FakePipeline(
        effects=[
            Image.new("RGB", (8, 8), color=(180, 180, 180)),
            RuntimeError("boom"),
        ]
    )

    GenerationService(root).generate_real_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    status = read_json(root / project.project_id / "metadata/generation_status.json")
    project_metadata = read_json(root / project.project_id / "metadata/project.json")
    assert status["status"] == "partial"
    assert status["completed_scenes"] == 1
    assert status["failed_scenes"] == 1
    assert manifest["assets"][0]["pipeline"] == "sdxl"
    assert manifest["assets"][0]["status"] == "success"
    assert (root / project.project_id / manifest["assets"][0]["output_path"]).is_file()
    assert manifest["assets"][1]["error_code"] == "SCENE_GENERATION_FAILED"
    assert project_metadata["status"] == ProjectStatus.GENERATION_PARTIAL.value


def test_real_sd15_continue_on_failure_false_stops_after_first_failure(
    monkeypatch, tmp_path
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(
        tmp_path,
        scene_count=2,
        profile=HardwareProfile.LOW_VRAM_4GB,
        continue_on_scene_failure=False,
    )
    pipeline = FakePipeline(effects=[RuntimeError("boom"), Image.new("RGB", (8, 8))])

    GenerationService(root).generate_real_sd15_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    assert status["status"] == "failed"
    assert len(status["scene_results"]) == 1
    assert len(pipeline.calls) == 1


def test_real_sdxl_continue_on_failure_false_stops_after_first_failure(
    monkeypatch, tmp_path
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(
        tmp_path,
        scene_count=2,
        continue_on_scene_failure=False,
    )
    pipeline = FakePipeline(effects=[RuntimeError("boom"), Image.new("RGB", (8, 8))])

    GenerationService(root).generate_real_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    assert status["status"] == "failed"
    assert len(status["scene_results"]) == 1
    assert len(pipeline.calls) == 1


def test_real_sd15_honors_cancel_requested_between_scenes(
    monkeypatch, tmp_path
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(
        tmp_path, scene_count=2, profile=HardwareProfile.LOW_VRAM_4GB
    )

    def request_cancel() -> None:
        job_service = GenerationJobService(root)
        current = job_service.get_status(project.project_id)
        assert current is not None
        job_service.save_status(
            project.project_id,
            current.model_copy(update={"status": GenerationJobStatus.CANCEL_REQUESTED}),
        )

    pipeline = FakePipeline(effects=[request_cancel, Image.new("RGB", (8, 8))])

    GenerationService(root).generate_real_sd15_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    project_metadata = read_json(root / project.project_id / "metadata/project.json")
    assert status["status"] == "cancelled"
    assert status["completed_scenes"] == 1
    assert len(pipeline.calls) == 1
    assert project_metadata["status"] == ProjectStatus.GENERATION_PARTIAL.value


def test_real_sdxl_honors_cancel_requested_between_scenes(
    monkeypatch, tmp_path
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(tmp_path, scene_count=2)

    def request_cancel() -> None:
        job_service = GenerationJobService(root)
        current = job_service.get_status(project.project_id)
        assert current is not None
        job_service.save_status(
            project.project_id,
            current.model_copy(update={"status": GenerationJobStatus.CANCEL_REQUESTED}),
        )

    pipeline = FakePipeline(effects=[request_cancel, Image.new("RGB", (8, 8))])

    GenerationService(root).generate_real_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    project_metadata = read_json(root / project.project_id / "metadata/project.json")
    assert status["status"] == "cancelled"
    assert status["completed_scenes"] == 1
    assert len(pipeline.calls) == 1
    assert project_metadata["status"] == ProjectStatus.GENERATION_PARTIAL.value


def test_real_sdxl_cpu_plan_fails_before_model_loading(tmp_path) -> None:
    root, project, job, _ = make_ready_project(tmp_path)
    factory = FakePipelineFactory()
    job_service = GenerationJobService(root)
    job_service.save_status(
        project.project_id,
        job.model_copy(
            update={
                "generation_plan": job.generation_plan.model_copy(
                    update={"device": "cpu", "torch_dtype": "float32"}
                )
            }
        ),
    )

    GenerationService(root).generate_real_images(
        project.project_id,
        job.job_id,
        pipeline_factory=factory,
    )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    project_metadata = read_json(root / project.project_id / "metadata/project.json")
    assert status["status"] == "failed"
    assert "GENERATION_PLAN_INVALID" in status["errors"][0]
    assert project_metadata["status"] == ProjectStatus.GENERATION_FAILED.value
    assert factory.load_calls == []


def test_real_generation_preserves_factory_app_error(monkeypatch, tmp_path) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(
        tmp_path, profile=HardwareProfile.LOW_VRAM_4GB
    )
    load_error = generation_service_module.AppError(
        code="MODEL_LOAD_FAILED",
        message="The local image model could not be loaded.",
        http_status=500,
        details={"model_id": "sd15-model"},
    )

    with pytest.raises(generation_service_module.AppError) as caught:
        GenerationService(root).generate_real_sd15_images(
            project.project_id,
            job.job_id,
            pipeline_factory=FakePipelineFactory(load_error=load_error),
        )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    assert caught.value.code == "MODEL_LOAD_FAILED"
    assert caught.value.message == "The local image model could not be loaded."
    assert caught.value.__cause__ is load_error
    assert status["status"] == "failed"
    assert "MODEL_LOAD_FAILED" in status["errors"][0]


def test_real_sdxl_generation_preserves_factory_app_error(
    monkeypatch, tmp_path
) -> None:
    install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(tmp_path)
    load_error = generation_service_module.AppError(
        code="MODEL_LOAD_FAILED",
        message="The local SDXL model could not be loaded.",
        http_status=500,
        details={"model_id": "sdxl-model"},
    )
    factory = FakePipelineFactory(load_error=load_error)

    with pytest.raises(generation_service_module.AppError) as caught:
        GenerationService(root).generate_real_images(
            project.project_id,
            job.job_id,
            pipeline_factory=factory,
        )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    assert caught.value.code == "MODEL_LOAD_FAILED"
    assert caught.value.message == "The local SDXL model could not be loaded."
    assert caught.value.__cause__ is load_error
    assert status["status"] == "failed"
    assert "MODEL_LOAD_FAILED" in status["errors"][0]
    assert factory.pipeline.calls == []


def test_real_sd15_cuda_oom_records_canonical_error(monkeypatch, tmp_path) -> None:
    fake_cuda = install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(
        tmp_path, profile=HardwareProfile.LOW_VRAM_4GB
    )
    pipeline = FakePipeline(effects=[fake_cuda.OutOfMemoryError("oom")])

    GenerationService(root).generate_real_sd15_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    assert fake_cuda.empty_cache_calls == 1
    assert status["scene_results"][0]["error_code"] == "CUDA_OUT_OF_MEMORY"
    assert manifest["assets"][0]["error_code"] == "CUDA_OUT_OF_MEMORY"


def test_real_sdxl_cuda_oom_records_canonical_error(monkeypatch, tmp_path) -> None:
    fake_cuda = install_fake_torch(monkeypatch)
    root, project, job, _ = make_ready_project(tmp_path)
    pipeline = FakePipeline(effects=[fake_cuda.OutOfMemoryError("oom")])

    GenerationService(root).generate_real_images(
        project.project_id,
        job.job_id,
        pipeline_factory=FakePipelineFactory(pipeline),
        seed_factory=lambda: 1234,
    )

    status = read_json(root / project.project_id / "metadata/generation_status.json")
    manifest = read_json(root / project.project_id / "outputs/manifest.json")
    assert fake_cuda.empty_cache_calls == 1
    assert status["scene_results"][0]["error_code"] == "CUDA_OUT_OF_MEMORY"
    assert "SD 1.5 fallback" in status["scene_results"][0]["error_message"]
    assert manifest["assets"][0]["pipeline"] == "sdxl"
    assert manifest["assets"][0]["error_code"] == "CUDA_OUT_OF_MEMORY"
