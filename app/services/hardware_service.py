from datetime import datetime, timezone
from importlib import import_module
from typing import Any

from app.schemas.generation import HardwareDetection, HardwareProfile


class HardwareService:
    """Detect local hardware without loading image generation models."""

    def __init__(self, torch_module: Any | None = None) -> None:
        self._torch_module = torch_module

    def detect_hardware(self) -> HardwareDetection:
        detected_at = datetime.now(timezone.utc)
        try:
            torch = self._get_torch_module()
            if torch is None:
                return self._cpu_fallback(
                    detected_at,
                    details={"warning": "torch is unavailable; using CPU fallback."},
                )

            try:
                cuda_available = bool(torch.cuda.is_available())
            except Exception as exc:
                return self._cpu_fallback(
                    detected_at,
                    details={
                        "warning": "CUDA availability could not be checked; using CPU fallback.",
                        "error_type": type(exc).__name__,
                    },
                )

            if not cuda_available:
                return self._cpu_fallback(detected_at)

            try:
                gpu_name = str(torch.cuda.get_device_name(0))
                properties = torch.cuda.get_device_properties(0)
                vram_gb = round(float(properties.total_memory) / (1024**3), 2)
            except Exception as exc:
                return self._cpu_fallback(
                    detected_at,
                    details={
                        "warning": (
                            "CUDA is available but GPU details could not be read; "
                            "using CPU fallback."
                        ),
                        "error_type": type(exc).__name__,
                    },
                )

            return HardwareDetection(
                device="cuda",
                gpu_name=gpu_name,
                vram_gb=vram_gb,
                cuda_available=True,
                hardware_profile=self.profile_for_vram(vram_gb),
                detected_at=detected_at,
            )
        except Exception as exc:
            return self._unknown(
                detected_at,
                details={
                    "warning": "Hardware detection failed unexpectedly.",
                    "error_type": type(exc).__name__,
                },
            )

    def _get_torch_module(self) -> Any | None:
        if self._torch_module is not None:
            return self._torch_module

        try:
            return import_module("torch")
        except Exception:
            return None

    @staticmethod
    def profile_for_vram(vram_gb: float) -> HardwareProfile:
        if vram_gb <= 4:
            return HardwareProfile.LOW_VRAM_4GB
        if vram_gb >= 12:
            return HardwareProfile.HIGH_VRAM_12GB_PLUS
        return HardwareProfile.MID_VRAM_6_8GB

    @staticmethod
    def _cpu_fallback(
        detected_at: datetime, *, details: dict[str, object] | None = None
    ) -> HardwareDetection:
        return HardwareDetection(
            device="cpu",
            gpu_name=None,
            vram_gb=0,
            cuda_available=False,
            hardware_profile=HardwareProfile.CPU_ONLY,
            detected_at=detected_at,
            details=details or {},
        )

    @staticmethod
    def _unknown(
        detected_at: datetime, *, details: dict[str, object] | None = None
    ) -> HardwareDetection:
        return HardwareDetection(
            device="unknown",
            gpu_name=None,
            vram_gb=0,
            cuda_available=False,
            hardware_profile=HardwareProfile.UNKNOWN,
            detected_at=detected_at,
            details=details or {},
        )
