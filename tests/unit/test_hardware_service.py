from types import SimpleNamespace

from app.schemas.generation import HardwareProfile
from app.services.hardware_service import HardwareService


class FakeCuda:
    def __init__(
        self,
        *,
        available: bool,
        total_memory: int = 0,
        gpu_name: str = "Example GPU",
        fail_on_details: bool = False,
    ) -> None:
        self.available = available
        self.total_memory = total_memory
        self.gpu_name = gpu_name
        self.fail_on_details = fail_on_details

    def is_available(self) -> bool:
        return self.available

    def current_device(self) -> int:
        if self.fail_on_details:
            raise RuntimeError("cuda details unavailable")
        return 0

    def get_device_name(self, device_index: int) -> str:
        assert device_index == 0
        return self.gpu_name

    def get_device_properties(self, device_index: int) -> SimpleNamespace:
        assert device_index == 0
        return SimpleNamespace(total_memory=self.total_memory)


def make_torch(cuda: FakeCuda) -> SimpleNamespace:
    return SimpleNamespace(cuda=cuda)


def gib(value: float) -> int:
    return int(value * 1024**3)


def test_cpu_only_system_returns_cpu_profile() -> None:
    hardware = HardwareService(
        torch_module=make_torch(FakeCuda(available=False))
    ).detect_hardware()

    assert hardware.device == "cpu"
    assert hardware.gpu_name is None
    assert hardware.vram_gb == 0
    assert hardware.cuda_available is False
    assert hardware.hardware_profile is HardwareProfile.CPU_ONLY
    assert "torch_dtype" not in hardware.model_dump(mode="json")


def test_cuda_system_returns_gpu_name_and_vram() -> None:
    hardware = HardwareService(
        torch_module=make_torch(
            FakeCuda(
                available=True,
                total_memory=gib(6),
                gpu_name="NVIDIA GeForce RTX 3060 Laptop GPU",
            )
        )
    ).detect_hardware()

    assert hardware.device == "cuda"
    assert hardware.gpu_name == "NVIDIA GeForce RTX 3060 Laptop GPU"
    assert hardware.vram_gb == 6
    assert hardware.cuda_available is True
    assert hardware.hardware_profile is HardwareProfile.MID_VRAM_6_8GB


def test_four_gb_or_below_maps_to_low_vram_profile() -> None:
    service = HardwareService()

    assert service.profile_for_vram(4) is HardwareProfile.LOW_VRAM_4GB
    assert service.profile_for_vram(3.5) is HardwareProfile.LOW_VRAM_4GB


def test_twelve_gb_or_above_maps_to_high_vram_profile() -> None:
    service = HardwareService()

    assert service.profile_for_vram(12) is HardwareProfile.HIGH_VRAM_12GB_PLUS
    assert service.profile_for_vram(24) is HardwareProfile.HIGH_VRAM_12GB_PLUS


def test_failed_cuda_detail_detection_returns_unknown_profile() -> None:
    hardware = HardwareService(
        torch_module=make_torch(
            FakeCuda(available=True, total_memory=gib(8), fail_on_details=True)
        )
    ).detect_hardware()

    assert hardware.device == "unknown"
    assert hardware.gpu_name is None
    assert hardware.vram_gb == 0
    assert hardware.cuda_available is False
    assert hardware.hardware_profile is HardwareProfile.UNKNOWN
