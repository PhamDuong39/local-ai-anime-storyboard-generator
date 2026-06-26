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
        torch = self._get_torch_module()
        if torch is None:
            return self._unknown(detected_at)

        try:
            cuda_available = bool(torch.cuda.is_available())
        except Exception:
            return self._unknown(detected_at)

        if not cuda_available:
            return HardwareDetection(
                device="cpu",
                gpu_name=None,
                vram_gb=0,
                cuda_available=False,
                hardware_profile=HardwareProfile.CPU_ONLY,
                detected_at=detected_at,
            )

        try:
            device_index = int(torch.cuda.current_device())
            gpu_name = str(torch.cuda.get_device_name(device_index))
            properties = torch.cuda.get_device_properties(device_index)
            vram_gb = round(float(properties.total_memory) / (1024**3), 2)
        except Exception:
            return self._unknown(detected_at)

        return HardwareDetection(
            device="cuda",
            gpu_name=gpu_name,
            vram_gb=vram_gb,
            cuda_available=True,
            hardware_profile=self.profile_for_vram(vram_gb),
            detected_at=detected_at,
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
    def _unknown(detected_at: datetime) -> HardwareDetection:
        return HardwareDetection(
            device="unknown",
            gpu_name=None,
            vram_gb=0,
            cuda_available=False,
            hardware_profile=HardwareProfile.UNKNOWN,
            detected_at=detected_at,
        )
