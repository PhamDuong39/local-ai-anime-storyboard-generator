from importlib import import_module
from typing import Any

from app.core.errors import AppError
from app.schemas.generation import PipelineKind
from app.schemas.jobs import GenerationPlan


ARCHIVED_SD15_MODEL_ID = "runwayml/stable-diffusion-v1-5"


class DiffusersPipelineFactory:
    """Lazily load and cache a Diffusers pipeline for one generation job."""

    def __init__(self) -> None:
        self._pipeline: object | None = None
        self._loaded_plan_key: str | None = None
        self._torch_module: Any | None = None

    def load(self, plan: GenerationPlan) -> object:
        self._validate_plan(plan)
        plan_key = self._plan_key(plan)
        if self._pipeline is not None and self._loaded_plan_key == plan_key:
            return self._pipeline

        self.unload()
        try:
            torch = import_module("torch")
            diffusers = import_module("diffusers")
            self._torch_module = torch

            if plan.pipeline is PipelineKind.SDXL:
                pipeline = self._load_sdxl(plan, torch, diffusers)
            elif plan.pipeline is PipelineKind.SD15:
                pipeline = self._load_sd15(plan, torch, diffusers)
            else:
                raise AppError(
                    code="GENERATION_PLAN_INVALID",
                    message="The saved generation plan is not valid.",
                    http_status=500,
                    details={"pipeline": str(plan.pipeline)},
                )
        except AppError:
            self.unload()
            raise
        except Exception as exc:
            self.unload()
            raise AppError(
                code="MODEL_LOAD_FAILED",
                message=(
                    "The local image model could not be loaded. Check your AI "
                    "dependencies and model configuration."
                ),
                http_status=500,
                details={
                    "pipeline": str(plan.pipeline.value),
                    "model_id": plan.model_id,
                    "device": plan.device,
                    "error_type": type(exc).__name__,
                },
            ) from exc

        self._pipeline = pipeline
        self._loaded_plan_key = plan_key
        return pipeline

    def unload(self) -> None:
        self._pipeline = None
        self._loaded_plan_key = None
        torch = self._torch_module
        if torch is None:
            return
        try:
            cuda = getattr(torch, "cuda", None)
            if cuda is not None and cuda.is_available():
                cuda.empty_cache()
        except Exception:
            return

    def _load_sdxl(self, plan: GenerationPlan, torch: Any, diffusers: Any) -> object:
        pipeline_class = diffusers.StableDiffusionXLPipeline
        dtype = self._resolve_dtype(plan, torch)
        kwargs = {
            "torch_dtype": dtype,
            "use_safetensors": True,
        }
        if plan.device == "cuda":
            try:
                pipeline = pipeline_class.from_pretrained(
                    plan.model_id,
                    **kwargs,
                    variant="fp16",
                )
            except Exception:
                pipeline = pipeline_class.from_pretrained(plan.model_id, **kwargs)
        else:
            pipeline = pipeline_class.from_pretrained(plan.model_id, **kwargs)

        pipeline = pipeline.to(plan.device)
        self._enable_if_available(pipeline, "enable_attention_slicing")
        self._enable_if_available(pipeline, "enable_vae_slicing")
        return pipeline

    def _load_sd15(self, plan: GenerationPlan, torch: Any, diffusers: Any) -> object:
        pipeline_class = diffusers.StableDiffusionPipeline
        pipeline = pipeline_class.from_pretrained(
            plan.model_id,
            torch_dtype=self._resolve_dtype(plan, torch),
            use_safetensors=True,
        )
        pipeline = pipeline.to(plan.device)
        self._enable_if_available(pipeline, "enable_attention_slicing")
        return pipeline

    def _validate_plan(self, plan: GenerationPlan) -> None:
        if plan.pipeline not in {PipelineKind.SD15, PipelineKind.SDXL}:
            raise AppError(
                code="GENERATION_PLAN_INVALID",
                message="The saved generation plan is not valid.",
                http_status=500,
                details={"pipeline": str(plan.pipeline)},
            )
        if not plan.model_id.strip():
            raise AppError(
                code="GENERATION_PLAN_INVALID",
                message="The saved generation plan is missing a model ID.",
                http_status=500,
                details={"pipeline": plan.pipeline.value},
            )
        if plan.model_id == ARCHIVED_SD15_MODEL_ID:
            raise AppError(
                code="GENERATION_PLAN_INVALID",
                message="The saved SD 1.5 model ID is no longer supported.",
                http_status=500,
                details={
                    "model_id": plan.model_id,
                    "replacement_model_id": (
                        "stable-diffusion-v1-5/stable-diffusion-v1-5"
                    ),
                },
            )
        if plan.device not in {"cpu", "cuda"}:
            raise AppError(
                code="GENERATION_PLAN_INVALID",
                message="The saved generation plan has an unsupported device.",
                http_status=500,
                details={"device": plan.device},
            )
        expected_dtype = "float16" if plan.device == "cuda" else "float32"
        if plan.torch_dtype != expected_dtype:
            raise AppError(
                code="GENERATION_PLAN_INVALID",
                message="The saved generation plan has an invalid dtype for the selected device.",
                http_status=500,
                details={
                    "device": plan.device,
                    "torch_dtype": plan.torch_dtype,
                    "expected_torch_dtype": expected_dtype,
                },
            )

    @staticmethod
    def _resolve_dtype(plan: GenerationPlan, torch: Any) -> object:
        return torch.float16 if plan.device == "cuda" else torch.float32

    @staticmethod
    def _enable_if_available(pipeline: object, method_name: str) -> None:
        method = getattr(pipeline, method_name, None)
        if callable(method):
            method()

    @staticmethod
    def _plan_key(plan: GenerationPlan) -> str:
        return f"{plan.pipeline.value}:{plan.model_id}:{plan.device}:{plan.torch_dtype}"
