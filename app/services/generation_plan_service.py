from dataclasses import dataclass

from app.schemas.generation import (
    GenerationMode,
    GenerationSettings,
    HardwareDetection,
    HardwareProfile,
    PipelineKind,
)
from app.schemas.jobs import GenerationPlan, JobCharacterConsistency
from app.schemas.manifest import RuntimeConsistencyMode
from app.schemas.project import OutputPresetId


@dataclass(frozen=True)
class GenerationPlanSelection:
    generation_plan: GenerationPlan
    character_consistency: JobCharacterConsistency


class GenerationPlanService:
    """Select a conservative local generation plan without loading models."""

    MID_VRAM_SAFE_SDXL_PRESETS = {
        OutputPresetId.LOW_VRAM_PREVIEW,
        OutputPresetId.LOW_VRAM_TINY,
    }

    def select(
        self,
        *,
        settings: GenerationSettings,
        hardware: HardwareDetection | None,
    ) -> GenerationPlanSelection:
        profile = hardware.hardware_profile if hardware else HardwareProfile.UNKNOWN
        detected_device = hardware.device if hardware else "unknown"
        mode = settings.generation_mode

        if settings.safety.force_low_vram_mode:
            return self._selection(
                settings=settings,
                pipeline=PipelineKind.SD15,
                model_id=settings.image_model.low_vram_image_model_id,
                device=self._safe_device(detected_device),
                disabled_reason="force_low_vram_mode",
                consistency_mode=RuntimeConsistencyMode.PROMPT_ONLY,
            )

        if mode is GenerationMode.CPU or profile is HardwareProfile.CPU_ONLY:
            return self._selection(
                settings=settings,
                pipeline=PipelineKind.SD15,
                model_id=settings.image_model.low_vram_image_model_id,
                device="cpu",
                disabled_reason="cpu_mode",
                consistency_mode=RuntimeConsistencyMode.PROMPT_ONLY,
            )

        if mode is GenerationMode.LOW_VRAM or profile is HardwareProfile.LOW_VRAM_4GB:
            return self._selection(
                settings=settings,
                pipeline=PipelineKind.SD15,
                model_id=settings.image_model.low_vram_image_model_id,
                device=self._cuda_or_safe_device(detected_device),
                disabled_reason="low_vram_default",
                consistency_mode=RuntimeConsistencyMode.FACEID_DISABLED_LOW_VRAM,
            )

        if profile is HardwareProfile.MID_VRAM_6_8GB:
            if self._mid_vram_allows_sdxl(settings):
                return self._selection(
                    settings=settings,
                    pipeline=PipelineKind.SDXL,
                    model_id=settings.image_model.image_model_id,
                    device=self._cuda_or_safe_device(detected_device),
                    disabled_reason="mid_vram_cautious_default",
                    consistency_mode=RuntimeConsistencyMode.PROMPT_ONLY,
                )
            return self._selection(
                settings=settings,
                pipeline=PipelineKind.SD15,
                model_id=settings.image_model.low_vram_image_model_id,
                device=self._cuda_or_safe_device(detected_device),
                disabled_reason="mid_vram_safe_fallback",
                consistency_mode=RuntimeConsistencyMode.PROMPT_ONLY,
            )

        if profile is HardwareProfile.HIGH_VRAM_12GB_PLUS:
            return self._selection(
                settings=settings,
                pipeline=PipelineKind.SDXL,
                model_id=settings.image_model.image_model_id,
                device=self._cuda_or_safe_device(detected_device),
                disabled_reason="faceid_unavailable",
                consistency_mode=RuntimeConsistencyMode.FACEID_UNAVAILABLE,
            )

        return self._selection(
            settings=settings,
            pipeline=PipelineKind.SD15,
            model_id=settings.image_model.low_vram_image_model_id,
            device=self._safe_device(detected_device),
            disabled_reason="unknown_hardware_safe_fallback",
            consistency_mode=RuntimeConsistencyMode.PROMPT_ONLY,
        )

    def _selection(
        self,
        *,
        settings: GenerationSettings,
        pipeline: PipelineKind,
        model_id: str,
        device: str,
        disabled_reason: str,
        consistency_mode: RuntimeConsistencyMode,
    ) -> GenerationPlanSelection:
        return GenerationPlanSelection(
            generation_plan=GenerationPlan(
                pipeline=pipeline,
                model_id=model_id,
                device=device,
                torch_dtype="float16" if device == "cuda" else "float32",
                output_preset_id=settings.output_preset.id,
            ),
            character_consistency=JobCharacterConsistency(
                method="ip-adapter-faceid",
                mode=consistency_mode,
                enabled=False,
                disabled_reason=disabled_reason,
            ),
        )

    def _mid_vram_allows_sdxl(self, settings: GenerationSettings) -> bool:
        return (
            settings.generation_mode is GenerationMode.QUALITY
            or settings.output_preset.id in self.MID_VRAM_SAFE_SDXL_PRESETS
        )

    @staticmethod
    def _cuda_or_safe_device(device: str) -> str:
        return "cuda" if device == "cuda" else GenerationPlanService._safe_device(device)

    @staticmethod
    def _safe_device(device: str) -> str:
        return device if device in {"cpu", "cuda"} else "cpu"
