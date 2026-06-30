from datetime import datetime, timezone

from app.schemas.generation import GenerationSettings, HardwareDetection, HardwareProfile
from app.schemas.generation import PipelineKind
from app.schemas.manifest import RuntimeConsistencyMode
from app.services.generation_plan_service import GenerationPlanService


NOW = datetime(2026, 6, 11, 10, 15, 30, tzinfo=timezone.utc)


def settings(
    *,
    generation_mode: str = "auto",
    output_preset_id: str = "youtube_standard",
    force_low_vram_mode: bool = False,
) -> GenerationSettings:
    preset_sizes = {
        "youtube_standard": (1280, 720, "16:9"),
        "low_vram_preview": (960, 540, "16:9"),
        "low_vram_tiny": (768, 432, "16:9"),
    }
    width, height, aspect_ratio = preset_sizes[output_preset_id]
    return GenerationSettings.model_validate(
        {
            "project_id": "valid-project",
            "output_preset": {
                "id": output_preset_id,
                "name": output_preset_id.replace("_", " ").title(),
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio,
            },
            "generation_mode": generation_mode,
            "image_model": {
                "primary_pipeline": "sdxl",
                "image_model_id": "sdxl-model",
                "low_vram_image_model_id": "sd15-model",
            },
            "defaults": {"negative_prompt": "text, watermark, logo"},
            "hardware": {
                "device": "unknown",
                "gpu_name": None,
                "vram_gb": 0,
                "cuda_available": False,
                "hardware_profile": "unknown",
                "detected_at": NOW,
            },
            "character_consistency": {"enabled": False},
            "safety": {"force_low_vram_mode": force_low_vram_mode},
            "updated_at": NOW,
        }
    )


def hardware(profile: HardwareProfile, *, device: str = "cuda") -> HardwareDetection:
    if profile is HardwareProfile.CPU_ONLY:
        device = "cpu"
    if profile is HardwareProfile.UNKNOWN:
        device = "unknown"
    return HardwareDetection(
        device=device,
        gpu_name=None if device != "cuda" else "Example GPU",
        vram_gb=0 if device != "cuda" else 8,
        cuda_available=device == "cuda",
        hardware_profile=profile,
        detected_at=NOW,
    )


def test_cpu_only_selects_sd15_cpu_with_prompt_fallback() -> None:
    selection = GenerationPlanService().select(
        settings=settings(),
        hardware=hardware(HardwareProfile.CPU_ONLY),
    )

    assert selection.generation_plan.pipeline is PipelineKind.SD15
    assert selection.generation_plan.model_id == "sd15-model"
    assert selection.generation_plan.device == "cpu"
    assert selection.generation_plan.torch_dtype == "float32"
    assert selection.character_consistency.enabled is False
    assert selection.character_consistency.disabled_reason == "cpu_mode"
    assert selection.character_consistency.mode is RuntimeConsistencyMode.PROMPT_ONLY


def test_low_vram_4gb_selects_sd15_and_disables_faceid() -> None:
    selection = GenerationPlanService().select(
        settings=settings(),
        hardware=hardware(HardwareProfile.LOW_VRAM_4GB),
    )

    assert selection.generation_plan.pipeline is PipelineKind.SD15
    assert selection.generation_plan.model_id == "sd15-model"
    assert selection.generation_plan.device == "cuda"
    assert selection.generation_plan.torch_dtype == "float16"
    assert selection.character_consistency.enabled is False
    assert selection.character_consistency.disabled_reason == "low_vram_default"
    assert (
        selection.character_consistency.mode
        is RuntimeConsistencyMode.FACEID_DISABLED_LOW_VRAM
    )


def test_mid_vram_auto_defaults_to_safer_sd15_path() -> None:
    selection = GenerationPlanService().select(
        settings=settings(),
        hardware=hardware(HardwareProfile.MID_VRAM_6_8GB),
    )

    assert selection.generation_plan.pipeline is PipelineKind.SD15
    assert selection.generation_plan.model_id == "sd15-model"
    assert selection.character_consistency.enabled is False
    assert selection.character_consistency.disabled_reason == "mid_vram_safe_fallback"


def test_mid_vram_quality_mode_allows_sdxl_without_faceid() -> None:
    selection = GenerationPlanService().select(
        settings=settings(generation_mode="quality"),
        hardware=hardware(HardwareProfile.MID_VRAM_6_8GB),
    )

    assert selection.generation_plan.pipeline is PipelineKind.SDXL
    assert selection.generation_plan.model_id == "sdxl-model"
    assert selection.character_consistency.enabled is False
    assert selection.character_consistency.disabled_reason == "mid_vram_cautious_default"


def test_mid_vram_safe_preset_allows_sdxl_without_faceid() -> None:
    selection = GenerationPlanService().select(
        settings=settings(output_preset_id="low_vram_preview"),
        hardware=hardware(HardwareProfile.MID_VRAM_6_8GB),
    )

    assert selection.generation_plan.pipeline is PipelineKind.SDXL
    assert selection.generation_plan.model_id == "sdxl-model"
    assert selection.generation_plan.output_preset_id.value == "low_vram_preview"
    assert selection.character_consistency.enabled is False


def test_high_vram_selects_sdxl_but_faceid_remains_unavailable_in_m9() -> None:
    selection = GenerationPlanService().select(
        settings=settings(),
        hardware=hardware(HardwareProfile.HIGH_VRAM_12GB_PLUS),
    )

    assert selection.generation_plan.pipeline is PipelineKind.SDXL
    assert selection.generation_plan.model_id == "sdxl-model"
    assert selection.character_consistency.enabled is False
    assert selection.character_consistency.disabled_reason == "faceid_unavailable"
    assert (
        selection.character_consistency.mode
        is RuntimeConsistencyMode.FACEID_UNAVAILABLE
    )


def test_force_low_vram_overrides_high_vram() -> None:
    selection = GenerationPlanService().select(
        settings=settings(force_low_vram_mode=True),
        hardware=hardware(HardwareProfile.HIGH_VRAM_12GB_PLUS),
    )

    assert selection.generation_plan.pipeline is PipelineKind.SD15
    assert selection.generation_plan.model_id == "sd15-model"
    assert selection.character_consistency.enabled is False
    assert selection.character_consistency.disabled_reason == "force_low_vram_mode"


def test_unknown_hardware_uses_safe_sd15_cpu_fallback() -> None:
    selection = GenerationPlanService().select(
        settings=settings(),
        hardware=hardware(HardwareProfile.UNKNOWN),
    )

    assert selection.generation_plan.pipeline is PipelineKind.SD15
    assert selection.generation_plan.model_id == "sd15-model"
    assert selection.generation_plan.device == "cpu"
    assert selection.generation_plan.torch_dtype == "float32"
    assert (
        selection.character_consistency.disabled_reason
        == "unknown_hardware_safe_fallback"
    )
