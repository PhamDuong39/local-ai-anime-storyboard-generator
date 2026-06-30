from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.schemas.jobs import GenerationPlan
from app.services import diffusers_pipeline_factory as factory_module
from app.services.diffusers_pipeline_factory import DiffusersPipelineFactory


class FakeCuda:
    def __init__(self, available: bool = False) -> None:
        self.available = available
        self.empty_cache_calls = 0

    def is_available(self) -> bool:
        return self.available

    def empty_cache(self) -> None:
        self.empty_cache_calls += 1


class FakePipeline:
    def __init__(self, model_id: str, **kwargs: object) -> None:
        self.model_id = model_id
        self.kwargs = kwargs
        self.device: str | None = None
        self.attention_slicing_enabled = False
        self.vae_slicing_enabled = False
        self.cpu_offload_enabled = False
        self.xformers_enabled = False

    def to(self, device: str) -> "FakePipeline":
        self.device = device
        return self

    def enable_attention_slicing(self) -> None:
        self.attention_slicing_enabled = True

    def enable_vae_slicing(self) -> None:
        self.vae_slicing_enabled = True

    def enable_model_cpu_offload(self) -> None:
        self.cpu_offload_enabled = True

    def enable_xformers_memory_efficient_attention(self) -> None:
        self.xformers_enabled = True


class FakePipelineClass:
    def __init__(self, *, fail_first_variant: bool = False) -> None:
        self.calls: list[dict[str, object]] = []
        self.instances: list[FakePipeline] = []
        self.fail_first_variant = fail_first_variant

    def from_pretrained(self, model_id: str, **kwargs: object) -> FakePipeline:
        self.calls.append({"model_id": model_id, **kwargs})
        if (
            self.fail_first_variant
            and len(self.calls) == 1
            and kwargs.get("variant") == "fp16"
        ):
            raise RuntimeError("fp16 variant missing")
        pipeline = FakePipeline(model_id, **kwargs)
        self.instances.append(pipeline)
        return pipeline


def plan(
    *,
    pipeline: str = "sd15",
    model_id: str = "stable-diffusion-v1-5/stable-diffusion-v1-5",
    device: str = "cpu",
    torch_dtype: str = "float32",
) -> GenerationPlan:
    return GenerationPlan.model_validate(
        {
            "pipeline": pipeline,
            "model_id": model_id,
            "device": device,
            "torch_dtype": torch_dtype,
            "output_preset_id": "low_vram_preview",
        }
    )


def install_fake_modules(monkeypatch, *, cuda_available: bool = False):
    fake_cuda = FakeCuda(available=cuda_available)
    fake_torch = SimpleNamespace(
        float16="torch.float16",
        float32="torch.float32",
        cuda=fake_cuda,
    )
    sd15_class = FakePipelineClass()
    sdxl_class = FakePipelineClass()
    fake_diffusers = SimpleNamespace(
        StableDiffusionPipeline=sd15_class,
        StableDiffusionXLPipeline=sdxl_class,
    )

    def fake_import_module(name: str):
        if name == "torch":
            return fake_torch
        if name == "diffusers":
            return fake_diffusers
        raise ImportError(name)

    monkeypatch.setattr(factory_module, "import_module", fake_import_module)
    return fake_torch, fake_diffusers, sd15_class, sdxl_class


def test_importing_factory_does_not_import_torch_or_diffusers() -> None:
    assert factory_module.__dict__["import_module"].__module__ == "importlib"


def test_sd15_cpu_load_uses_float32_and_attention_slicing(monkeypatch) -> None:
    _, _, sd15_class, _ = install_fake_modules(monkeypatch)

    loaded = DiffusersPipelineFactory().load(plan())

    assert sd15_class.calls == [
        {
            "model_id": "stable-diffusion-v1-5/stable-diffusion-v1-5",
            "torch_dtype": "torch.float32",
            "use_safetensors": True,
        }
    ]
    assert loaded.device == "cpu"
    assert loaded.attention_slicing_enabled is True
    assert loaded.vae_slicing_enabled is False
    assert loaded.cpu_offload_enabled is False
    assert loaded.xformers_enabled is False


def test_sd15_cuda_load_uses_float16(monkeypatch) -> None:
    _, _, sd15_class, _ = install_fake_modules(monkeypatch, cuda_available=True)

    loaded = DiffusersPipelineFactory().load(plan(device="cuda", torch_dtype="float16"))

    assert sd15_class.calls[0]["torch_dtype"] == "torch.float16"
    assert loaded.device == "cuda"
    assert loaded.attention_slicing_enabled is True


def test_sdxl_cuda_tries_fp16_variant_then_falls_back(monkeypatch) -> None:
    _, fake_diffusers, _, _ = install_fake_modules(monkeypatch, cuda_available=True)
    sdxl_class = FakePipelineClass(fail_first_variant=True)
    fake_diffusers.StableDiffusionXLPipeline = sdxl_class

    loaded = DiffusersPipelineFactory().load(
        plan(
            pipeline="sdxl",
            model_id="stabilityai/stable-diffusion-xl-base-1.0",
            device="cuda",
            torch_dtype="float16",
        )
    )

    assert len(sdxl_class.calls) == 2
    assert sdxl_class.calls[0]["variant"] == "fp16"
    assert "variant" not in sdxl_class.calls[1]
    assert loaded.device == "cuda"
    assert loaded.attention_slicing_enabled is True
    assert loaded.vae_slicing_enabled is True
    assert loaded.cpu_offload_enabled is False
    assert loaded.xformers_enabled is False


def test_sdxl_cpu_does_not_request_fp16_variant(monkeypatch) -> None:
    _, _, _, sdxl_class = install_fake_modules(monkeypatch)

    DiffusersPipelineFactory().load(
        plan(
            pipeline="sdxl",
            model_id="stabilityai/stable-diffusion-xl-base-1.0",
        )
    )

    assert sdxl_class.calls == [
        {
            "model_id": "stabilityai/stable-diffusion-xl-base-1.0",
            "torch_dtype": "torch.float32",
            "use_safetensors": True,
        }
    ]


def test_same_plan_returns_cached_pipeline(monkeypatch) -> None:
    _, _, sd15_class, _ = install_fake_modules(monkeypatch)
    factory = DiffusersPipelineFactory()
    generation_plan = plan()

    first = factory.load(generation_plan)
    second = factory.load(generation_plan)

    assert first is second
    assert len(sd15_class.calls) == 1


def test_different_plan_reloads_pipeline(monkeypatch) -> None:
    _, _, sd15_class, _ = install_fake_modules(monkeypatch)
    factory = DiffusersPipelineFactory()

    first = factory.load(plan())
    second = factory.load(plan(device="cuda", torch_dtype="float16"))

    assert first is not second
    assert len(sd15_class.calls) == 2


def test_unload_clears_cache_and_cuda_cache(monkeypatch) -> None:
    fake_torch, _, _, _ = install_fake_modules(monkeypatch, cuda_available=True)
    factory = DiffusersPipelineFactory()
    factory.load(plan(device="cuda", torch_dtype="float16"))

    factory.unload()

    assert fake_torch.cuda.empty_cache_calls == 1
    assert factory._pipeline is None
    assert factory._loaded_plan_key is None


@pytest.mark.parametrize(
    ("device", "torch_dtype"),
    [
        ("cpu", "float16"),
        ("cuda", "float32"),
    ],
)
def test_dtype_device_mismatch_raises_plan_invalid(
    device: str, torch_dtype: str
) -> None:
    with pytest.raises(AppError) as caught:
        DiffusersPipelineFactory().load(plan(device=device, torch_dtype=torch_dtype))

    assert caught.value.code == "GENERATION_PLAN_INVALID"


def test_archived_sd15_model_id_raises_plan_invalid() -> None:
    with pytest.raises(AppError) as caught:
        DiffusersPipelineFactory().load(plan(model_id="runwayml/stable-diffusion-v1-5"))

    assert caught.value.code == "GENERATION_PLAN_INVALID"
    assert (
        "stable-diffusion-v1-5/stable-diffusion-v1-5"
        in caught.value.details["replacement_model_id"]
    )


def test_import_failure_raises_model_load_failed(monkeypatch) -> None:
    def fail_import_module(name: str):
        raise ImportError(name)

    monkeypatch.setattr(factory_module, "import_module", fail_import_module)

    with pytest.raises(AppError) as caught:
        DiffusersPipelineFactory().load(plan())

    assert caught.value.code == "MODEL_LOAD_FAILED"
    assert "could not be loaded" in caught.value.message
    assert caught.value.__cause__ is not None
    assert caught.value.details["error_type"] == "ImportError"


def test_from_pretrained_failure_raises_model_load_failed(monkeypatch) -> None:
    _, _, sd15_class, _ = install_fake_modules(monkeypatch)

    def fail_from_pretrained(model_id: str, **kwargs: object) -> FakePipeline:
        raise RuntimeError("download failed")

    sd15_class.from_pretrained = fail_from_pretrained

    with pytest.raises(AppError) as caught:
        DiffusersPipelineFactory().load(plan())

    assert caught.value.code == "MODEL_LOAD_FAILED"
    assert caught.value.__cause__ is not None
    assert caught.value.details["error_type"] == "RuntimeError"
