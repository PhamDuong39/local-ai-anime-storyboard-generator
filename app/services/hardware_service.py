import os
import platform
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

from app.schemas.generation import HardwareDetection, HardwareProfile


class HardwareService:
    """Detect local hardware without loading image generation models."""

    CPUINFO_PATH = Path("/proc/cpuinfo")

    def __init__(self, torch_module: Any | None = None) -> None:
        self._torch_module = torch_module

    def detect_hardware(self) -> HardwareDetection:
        detected_at = datetime.now(timezone.utc)
        cpu_info = self._detect_cpu_info()
        try:
            torch = self._get_torch_module()
            if torch is None:
                return self._cpu_fallback(
                    detected_at,
                    cpu_info=cpu_info,
                    details={"warning": "torch is unavailable; using CPU fallback."},
                )

            try:
                cuda_available = bool(torch.cuda.is_available())
            except Exception as exc:
                return self._cpu_fallback(
                    detected_at,
                    cpu_info=cpu_info,
                    details={
                        "warning": "CUDA availability could not be checked; using CPU fallback.",
                        "error_type": type(exc).__name__,
                    },
                )

            if not cuda_available:
                return self._cpu_fallback(detected_at, cpu_info=cpu_info)

            try:
                gpu_name = str(torch.cuda.get_device_name(0))
                properties = torch.cuda.get_device_properties(0)
                vram_gb = round(float(properties.total_memory) / (1024**3), 2)
            except Exception as exc:
                return self._cpu_fallback(
                    detected_at,
                    cpu_info=cpu_info,
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
                **cpu_info,
                vram_gb=vram_gb,
                cuda_available=True,
                hardware_profile=self.profile_for_vram(vram_gb),
                detected_at=detected_at,
            )
        except Exception as exc:
            return self._unknown(
                detected_at,
                cpu_info=cpu_info,
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

    def _cpu_fallback(
        self,
        detected_at: datetime,
        *,
        cpu_info: dict[str, object | None] | None = None,
        details: dict[str, object] | None = None,
    ) -> HardwareDetection:
        resolved_cpu_info = cpu_info if cpu_info is not None else self._detect_cpu_info()
        return HardwareDetection(
            device="cpu",
            gpu_name=None,
            **resolved_cpu_info,
            vram_gb=0,
            cuda_available=False,
            hardware_profile=HardwareProfile.CPU_ONLY,
            detected_at=detected_at,
            details=details or {},
        )

    def _unknown(
        self,
        detected_at: datetime,
        *,
        cpu_info: dict[str, object | None] | None = None,
        details: dict[str, object] | None = None,
    ) -> HardwareDetection:
        resolved_cpu_info = cpu_info if cpu_info is not None else self._detect_cpu_info()
        return HardwareDetection(
            device="unknown",
            gpu_name=None,
            **resolved_cpu_info,
            vram_gb=0,
            cuda_available=False,
            hardware_profile=HardwareProfile.UNKNOWN,
            detected_at=detected_at,
            details=details or {},
        )

    def _detect_cpu_info(self) -> dict[str, object | None]:
        """Best-effort CPU metadata; never block hardware detection."""
        try:
            cpu_arch = self._clean_optional(platform.machine())
        except Exception:
            cpu_arch = None
        return {
            "cpu_model": self._detect_cpu_model(),
            "cpu_arch": cpu_arch,
            **self._detect_cpu_cores(),
        }

    def _detect_cpu_model(self) -> str | None:
        model_from_proc = self._detect_linux_cpu_model()
        if model_from_proc is not None:
            return model_from_proc
        try:
            return self._clean_optional(platform.processor())
        except Exception:
            return None

    def _detect_linux_cpu_model(self) -> str | None:
        try:
            if not self.CPUINFO_PATH.is_file():
                return None
            for line in self.CPUINFO_PATH.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines():
                key, separator, value = line.partition(":")
                if separator and key.strip().lower() == "model name":
                    return self._clean_optional(value)
        except OSError:
            return None
        return None

    def _detect_cpu_cores(self) -> dict[str, int | None]:
        physical_cores: int | None = None
        logical_cores: int | None = None
        psutil = self._get_optional_module("psutil")
        if psutil is not None:
            try:
                physical_cores = self._positive_int_or_none(
                    psutil.cpu_count(logical=False)
                )
                logical_cores = self._positive_int_or_none(
                    psutil.cpu_count(logical=True)
                )
            except Exception:
                physical_cores = None
                logical_cores = None

        if logical_cores is None:
            logical_cores = self._positive_int_or_none(os.cpu_count())

        return {
            "physical_cores": physical_cores,
            "logical_cores": logical_cores,
        }

    def _get_optional_module(self, module_name: str) -> Any | None:
        try:
            return import_module(module_name)
        except Exception:
            return None

    @staticmethod
    def _clean_optional(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _positive_int_or_none(value: object) -> int | None:
        try:
            integer = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return integer if integer > 0 else None
