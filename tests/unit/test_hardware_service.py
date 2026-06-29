from types import SimpleNamespace

from app.schemas.generation import HardwareProfile
import app.services.hardware_service as hardware_service_module
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

    def get_device_name(self, device_index: int) -> str:
        assert device_index == 0
        if self.fail_on_details:
            raise RuntimeError("cuda details unavailable")
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


def test_torch_unavailable_returns_cpu_profile(monkeypatch) -> None:
    def fail_import(name: str) -> object:
        assert name == "torch"
        raise ImportError("torch unavailable")

    monkeypatch.setattr(hardware_service_module, "import_module", fail_import)

    hardware = HardwareService().detect_hardware()

    assert hardware.device == "cpu"
    assert hardware.gpu_name is None
    assert hardware.vram_gb == 0
    assert hardware.cuda_available is False
    assert hardware.hardware_profile is HardwareProfile.CPU_ONLY
    assert "torch is unavailable" in str(hardware.details["warning"])


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


def test_cuda_four_gb_or_below_maps_to_low_vram_profile() -> None:
    hardware = HardwareService(
        torch_module=make_torch(FakeCuda(available=True, total_memory=gib(4)))
    ).detect_hardware()

    assert hardware.device == "cuda"
    assert hardware.vram_gb == 4
    assert hardware.hardware_profile is HardwareProfile.LOW_VRAM_4GB


def test_cuda_six_to_eight_gb_maps_to_mid_vram_profile() -> None:
    hardware = HardwareService(
        torch_module=make_torch(FakeCuda(available=True, total_memory=gib(8)))
    ).detect_hardware()

    assert hardware.device == "cuda"
    assert hardware.vram_gb == 8
    assert hardware.hardware_profile is HardwareProfile.MID_VRAM_6_8GB


def test_cuda_twelve_gb_or_above_maps_to_high_vram_profile() -> None:
    hardware = HardwareService(
        torch_module=make_torch(FakeCuda(available=True, total_memory=gib(12)))
    ).detect_hardware()

    assert hardware.device == "cuda"
    assert hardware.vram_gb == 12
    assert hardware.hardware_profile is HardwareProfile.HIGH_VRAM_12GB_PLUS


def test_cuda_detail_failure_returns_cpu_fallback() -> None:
    hardware = HardwareService(
        torch_module=make_torch(
            FakeCuda(available=True, total_memory=gib(8), fail_on_details=True)
        )
    ).detect_hardware()

    assert hardware.device == "cpu"
    assert hardware.gpu_name is None
    assert hardware.vram_gb == 0
    assert hardware.cuda_available is False
    assert hardware.hardware_profile is HardwareProfile.CPU_ONLY
