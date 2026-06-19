# skill-diffusers-image-generation.md

**Skill for:** Codex Agent  
**Applies to:** `app/services/pipeline_factory.py`, `app/services/generation_service.py`, `app/services/hardware_service.py`, `app/services/dependency_service.py`, `app/services/manifest_service.py`, `app/services/generation_job_service.py`  
**Primary spec:** `docs/09-generation-pipeline.md`  
**Related specs:** `docs/06-techstack.md`, `docs/07-architecture.md`, `docs/14-mvp-task-breakdown.md`, `AGENTS.md`  
**Phase:** Phase 1 MVP

---

## 1. What This Skill Covers

Concrete, copy-ready implementation patterns for:

- Hardware detection with PyTorch.
- Safe generation plan selection.
- Loading SDXL and SD 1.5 pipelines in Diffusers 0.38.
- Memory optimizations for Windows GPU.
- Running a generation call.
- CUDA OOM handling.
- A mock pipeline for tests and M7 milestone.
- IP-Adapter-FaceID weight loading, face embedding extraction, and FaceID generation call.
- Multi-character FaceID limitation handling.
- `PipelineFactory` pattern.
- Dependency checks for FaceID.
- Per-scene manifest/status updates.
- Error-code mapping.

This skill file replaces online Diffusers examples that may be outdated. Always prefer patterns from this file over search results.

---

## 2. Read Before Writing Any Code

### 2.1 Hard Rules

- **Do not load any model at app startup.** Load lazily when a generation job starts.
- **Do not use `runwayml/stable-diffusion-v1-5`.** That model ID is archived. Use `stable-diffusion-v1-5/stable-diffusion-v1-5`.
- **Do not attempt SDXL + FaceID on `low_vram_4gb`.** Use SD 1.5 + prompt hints only.
- **Do not enable IP-Adapter-FaceID by default on `mid_vram_6_8gb`.** Enable it only when explicitly forced and dependency checks pass.
- **Do not use `torch.float16` on CPU.** Use `torch.float32`.
- **Do not use `enable_model_cpu_offload()` by default.** It is slower for scene-by-scene generation and can cause issues. Use attention slicing and VAE slicing instead.
- **Do not add xFormers as a hard dependency.** The MVP must work without it.
- **Do not batch multiple scenes.** Generate one scene at a time.
- **Do not show raw Python exceptions in the UI.** Map to user-facing error messages.
- **Do not silently skip manifest/status updates.** Every scene success or failure must be recorded.
- **Do not claim FaceID was used for every character if only one character used it.** Persist the real behavior in the manifest.

### 2.2 Implementation Order

Follow this order. Do not skip ahead to FaceID before SD 1.5 works.

```text
1. MockPipeline (no real models, tests pass)
2. HardwareService (detect profile, including unknown fallback)
3. GenerationPlan selection
4. SD 1.5 pipeline loading + generation
5. SDXL pipeline loading + generation
6. Per-scene status + manifest updates
7. FaceID dependency check
8. FaceID loading + single-primary-character generation
9. Optional multi-character improvement only after explicit testing
```

### 2.3 Scope Boundary

This skill is for **image generation only**. Do not add video generation, voice, lip-sync, subtitles, timeline export, ComfyUI graphs, LoRA training, cloud rendering, queues, or microservices.

---

## 3. Required Packages

### 3.1 GPU Path — `requirements/ai-cu128.txt`

```text
torch==2.7.*
torchvision==compatible-with-installed-torch
torchaudio==compatible-with-installed-torch
diffusers>=0.38,<0.39
transformers>=5.10,<6
accelerate>=1.13,<2
safetensors>=0.5,<1
huggingface-hub>=0.33,<1
numpy>=2,<3
insightface>=0.7,<1
onnxruntime-gpu>=1.26,<2
opencv-python-headless>=4.10,<5
```

### 3.2 CPU Path — `requirements/ai-cpu.txt`

```text
torch==2.7.*
torchvision==compatible-with-installed-torch
torchaudio==compatible-with-installed-torch
diffusers>=0.38,<0.39
transformers>=5.10,<6
accelerate>=1.13,<2
safetensors>=0.5,<1
huggingface-hub>=0.33,<1
numpy>=2,<3
insightface>=0.7,<1
onnxruntime>=1.26,<2
opencv-python-headless>=4.10,<5
```

`Pillow` is required by image validation and the mock pipeline. It can live in `requirements/base.txt`, as defined by the task breakdown.

**Do not install both `onnxruntime` and `onnxruntime-gpu` in the same environment.**

---

## 4. Hardware Detection

Use PyTorch for detection. Do not load Diffusers models during detection.

`HardwareService` should return a small dict or Pydantic model that can be stored in `generation_settings.json`.

```python
# app/services/hardware_service.py
from datetime import datetime, timezone
import torch

from app.schemas.generation import HardwareProfile


def detect_hardware() -> dict:
    detected_at = datetime.now(timezone.utc).isoformat()

    try:
        if torch.cuda.is_available():
            index = 0
            props = torch.cuda.get_device_properties(index)
            vram_gb = round(props.total_memory / (1024 ** 3), 2)
            profile = _classify_profile(vram_gb)
            return {
                "device": "cuda",
                "gpu_name": props.name,
                "vram_gb": vram_gb,
                "cuda_available": True,
                "hardware_profile": profile,
                "detected_at": detected_at,
            }

        return {
            "device": "cpu",
            "gpu_name": None,
            "vram_gb": 0.0,
            "cuda_available": False,
            "hardware_profile": HardwareProfile.cpu_only,
            "detected_at": detected_at,
        }
    except Exception:
        return {
            "device": "cpu",
            "gpu_name": None,
            "vram_gb": 0.0,
            "cuda_available": False,
            "hardware_profile": HardwareProfile.unknown,
            "detected_at": detected_at,
        }


def _classify_profile(vram_gb: float) -> str:
    if vram_gb <= 4.0:
        return HardwareProfile.low_vram_4gb
    if vram_gb <= 8.0:
        return HardwareProfile.mid_vram_6_8gb
    if vram_gb >= 12.0:
        return HardwareProfile.high_vram_12gb_plus
    # 8–12GB stays cautious in Phase 1.
    return HardwareProfile.mid_vram_6_8gb
```

`torch_dtype` is **not** part of hardware detection output. It is derived in `GenerationPlan` after the target device is known.

```python
def resolve_dtype(device: str):
    import torch
    return torch.float16 if device == "cuda" else torch.float32
```

---

## 5. Generation Plan Selection

`GenerationPlan` decides which pipeline to load and whether FaceID is allowed.

### 5.1 Canonical Values

```text
PipelineKind.sdxl
PipelineKind.sd15

HardwareProfile.cpu_only
HardwareProfile.low_vram_4gb
HardwareProfile.mid_vram_6_8gb
HardwareProfile.high_vram_12gb_plus
HardwareProfile.unknown

FaceID mode values:
faceid_enabled
faceid_disabled_low_vram
faceid_unavailable
prompt_only
```

### 5.2 Decision Table

| Hardware / Mode | Image Pipeline | Recommended Preset | FaceID Default |
|---|---|---|---|
| `cpu_only` | SD 1.5 CPU fallback | `low_vram_preview` or `low_vram_tiny` | Disabled |
| `low_vram_4gb` | SD 1.5 CUDA fallback | `low_vram_preview` | Disabled |
| `mid_vram_6_8gb` | SDXL with optimizations or SD 1.5 fallback | `youtube_standard` cautiously | Disabled unless forced + checks pass |
| `high_vram_12gb_plus` | SDXL | `youtube_standard` or `youtube_high` | Enabled if dependencies pass |
| `unknown` | SD 1.5 safe fallback | `low_vram_preview` | Disabled |
| `force_low_vram=true` | SD 1.5 fallback | `low_vram_preview` | Disabled |

### 5.3 Pseudocode

```python
# app/services/generation_service.py or app/services/generation_plan_service.py
from app.schemas.generation import GenerationPlan, PipelineKind, HardwareProfile


def select_generation_plan(settings, hardware, dependency_status) -> GenerationPlan:
    if settings.force_low_vram_mode:
        return GenerationPlan(
            pipeline=PipelineKind.sd15,
            model_id=settings.low_vram_image_model_id,
            device="cuda" if hardware.device == "cuda" else "cpu",
            torch_dtype="float16" if hardware.device == "cuda" else "float32",
            faceid_enabled=False,
            character_consistency_mode="faceid_disabled_low_vram",
            faceid_disabled_reason="force_low_vram_mode",
        )

    if settings.generation_mode == "cpu" or hardware.hardware_profile == HardwareProfile.cpu_only:
        return GenerationPlan(
            pipeline=PipelineKind.sd15,
            model_id=settings.low_vram_image_model_id,
            device="cpu",
            torch_dtype="float32",
            faceid_enabled=False,
            character_consistency_mode="prompt_only",
            faceid_disabled_reason="cpu_mode",
        )

    if hardware.hardware_profile == HardwareProfile.low_vram_4gb:
        return GenerationPlan(
            pipeline=PipelineKind.sd15,
            model_id=settings.low_vram_image_model_id,
            device="cuda",
            torch_dtype="float16",
            faceid_enabled=False,
            character_consistency_mode="faceid_disabled_low_vram",
            faceid_disabled_reason="low_vram_default",
        )

    if hardware.hardware_profile == HardwareProfile.mid_vram_6_8gb:
        faceid_enabled = (
            settings.enable_ip_adapter_faceid == "force"
            and dependency_status.faceid_available
        )
        return GenerationPlan(
            pipeline=PipelineKind.sdxl,
            model_id=settings.image_model_id,
            device="cuda",
            torch_dtype="float16",
            faceid_enabled=faceid_enabled,
            character_consistency_mode="faceid_enabled" if faceid_enabled else "prompt_only",
            faceid_disabled_reason=None if faceid_enabled else "mid_vram_cautious_default",
        )

    if hardware.hardware_profile == HardwareProfile.high_vram_12gb_plus:
        faceid_enabled = (
            settings.enable_ip_adapter_faceid in ["auto", "true", "force"]
            and dependency_status.faceid_available
        )
        return GenerationPlan(
            pipeline=PipelineKind.sdxl,
            model_id=settings.image_model_id,
            device="cuda",
            torch_dtype="float16",
            faceid_enabled=faceid_enabled,
            character_consistency_mode="faceid_enabled" if faceid_enabled else "faceid_unavailable",
            faceid_disabled_reason=None if faceid_enabled else "faceid_unavailable",
        )

    return GenerationPlan(
        pipeline=PipelineKind.sd15,
        model_id=settings.low_vram_image_model_id,
        device="cpu" if hardware.device != "cuda" else "cuda",
        torch_dtype="float32" if hardware.device != "cuda" else "float16",
        faceid_enabled=False,
        character_consistency_mode="prompt_only",
        faceid_disabled_reason="unknown_hardware_safe_fallback",
    )
```

### 5.4 Model IDs

Use these defaults unless the project explicitly changes them:

```env
IMAGE_MODEL_ID=stabilityai/stable-diffusion-xl-base-1.0
LOW_VRAM_IMAGE_MODEL_ID=stable-diffusion-v1-5/stable-diffusion-v1-5
```

---

## 6. Pipeline Loading

### 6.1 SDXL Pipeline

```python
import torch
from diffusers import StableDiffusionXLPipeline


def load_sdxl_pipeline(model_id: str, device: str) -> StableDiffusionXLPipeline:
    try:
        pipeline = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            use_safetensors=True,
            variant="fp16",
        )
    except Exception:
        # Some models do not publish an fp16 variant.
        pipeline = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            use_safetensors=True,
        )

    pipeline = pipeline.to(device)
    pipeline.enable_attention_slicing()
    pipeline.enable_vae_slicing()
    return pipeline
```

### 6.2 SD 1.5 Pipeline — Low-VRAM Fallback

```python
import torch
from diffusers import StableDiffusionPipeline


def load_sd15_pipeline(model_id: str, device: str) -> StableDiffusionPipeline:
    dtype = torch.float16 if device == "cuda" else torch.float32
    pipeline = StableDiffusionPipeline.from_pretrained(
        model_id,
        torch_dtype=dtype,
        use_safetensors=True,
    )
    pipeline = pipeline.to(device)
    pipeline.enable_attention_slicing()
    return pipeline
```

Correct SD 1.5 model ID:

```python
model_id = "stable-diffusion-v1-5/stable-diffusion-v1-5"
```

Do not use `runwayml/stable-diffusion-v1-5`.

### 6.3 CPU Mode

CPU mode always uses SD 1.5 with `torch.float32`. Do not use SDXL on CPU.

```python
pipeline = load_sd15_pipeline(
    model_id="stable-diffusion-v1-5/stable-diffusion-v1-5",
    device="cpu",
)
```

### 6.4 Memory Optimizations Summary

| Optimization | When to use | How |
|---|---|---|
| `torch.float16` | CUDA only | Set in `from_pretrained(torch_dtype=...)` |
| `torch.float32` | CPU only | Set in `from_pretrained(torch_dtype=...)` |
| Attention slicing | All pipelines | `pipeline.enable_attention_slicing()` |
| VAE slicing | SDXL | `pipeline.enable_vae_slicing()` |
| CPU offload | Avoid in MVP | Do not enable by default |
| xFormers | Optional only | Do not require it |
| `torch.compile` | Do not use in MVP | Too experimental on Windows |

---

## 7. Generation Call

### 7.1 Standard Call — SDXL and SD 1.5

Both pipelines use the same core call signature.

```python
import torch


def generate_image(pipeline, prompt_package: dict) -> "PIL.Image.Image":
    generator = torch.Generator(device=pipeline.device.type).manual_seed(
        prompt_package["seed"]
    )
    result = pipeline(
        prompt=prompt_package["positive_prompt"],
        negative_prompt=prompt_package["negative_prompt"],
        width=prompt_package["width"],
        height=prompt_package["height"],
        num_inference_steps=prompt_package["num_inference_steps"],
        guidance_scale=prompt_package["guidance_scale"],
        generator=generator,
    )
    if not result.images:
        raise RuntimeError("Diffusers returned no images.")
    return result.images[0]
```

### 7.2 CUDA OOM Handling

Catch `torch.cuda.OutOfMemoryError` specifically. Do not catch all `Exception` and silently continue.

```python
import torch
from app.core.errors import RecoverableSceneGenerationError, GlobalGenerationError


def generate_with_oom_guard(pipeline, prompt_package: dict, scene_index: int):
    try:
        return generate_image(pipeline, prompt_package)
    except torch.cuda.OutOfMemoryError as exc:
        torch.cuda.empty_cache()
        scene_number = prompt_package.get("scene_number", "?")
        if scene_index == 0:
            raise GlobalGenerationError(
                code="CUDA_OUT_OF_MEMORY",
                message=(
                    "GPU ran out of memory on the first scene. "
                    "Switch to Low VRAM Preview or SD 1.5."
                ),
            ) from exc
        raise RecoverableSceneGenerationError(
            code="CUDA_OUT_OF_MEMORY",
            message=(
                f"Your GPU ran out of memory while generating scene {scene_number}. "
                "Try Low VRAM Preview or SD 1.5 fallback."
            ),
        ) from exc
    except Exception as exc:
        scene_number = prompt_package.get("scene_number", "?")
        raise RecoverableSceneGenerationError(
            code="SCENE_GENERATION_FAILED",
            message=f"Image generation failed for scene {scene_number}.",
        ) from exc
```

---

## 8. Mock Pipeline — Tests and M7

Use this mock for all tests and for the M7 milestone. It requires no GPU, no model download, and returns a valid PIL image.

```python
# app/services/pipeline_factory_mock.py
from PIL import Image


class MockPipeline:
    """
    Drop-in fake for StableDiffusionXLPipeline and StableDiffusionPipeline.
    Returns a small gray PIL image. Requires no GPU or model files.
    """

    def __init__(self, device: str = "cpu"):
        self._device = device

    @property
    def device(self):
        return type("_Dev", (), {"type": self._device})()

    def __call__(self, prompt: str, **kwargs) -> "MockOutput":
        width = kwargs.get("width", 512)
        height = kwargs.get("height", 512)
        image = Image.new("RGB", (width, height), color=(180, 180, 180))
        return _MockOutput(images=[image])

    def to(self, device: str) -> "MockPipeline":
        self._device = device
        return self

    def enable_attention_slicing(self) -> None:
        pass

    def enable_vae_slicing(self) -> None:
        pass

    def load_ip_adapter(self, *args, **kwargs) -> None:
        pass

    def set_ip_adapter_scale(self, scale: float) -> None:
        pass


class _MockOutput:
    def __init__(self, images: list):
        self.images = images
```

`PipelineFactory` should return `MockPipeline` when `USE_MOCK_PIPELINE=true` is set.

---

## 9. IP-Adapter-FaceID

Only implement FaceID after SD 1.5 and SDXL generation are working end-to-end. FaceID is hardware-conditional and must not break prompt-only fallback.

### 9.1 Weight Files

HuggingFace repo:

```text
h94/IP-Adapter-FaceID
```

| Pipeline | Weight file |
|---|---|
| SD 1.5 | `ip-adapter-faceid_sd15.bin` |
| SDXL | `ip-adapter-faceid_sdxl.bin` |

These weights download automatically from HuggingFace Hub on first use. No manual download is required if `huggingface-hub` is installed.

### 9.2 Loading FaceID onto a Pipeline

Call `load_ip_adapter` after the base pipeline is loaded and moved to device. The `image_encoder_folder=None` argument is **required** because FaceID uses InsightFace embeddings, not a CLIP image encoder.

SD 1.5:

```python
pipeline.load_ip_adapter(
    "h94/IP-Adapter-FaceID",
    subfolder=".",
    weight_name="ip-adapter-faceid_sd15.bin",
    image_encoder_folder=None,
)
pipeline.set_ip_adapter_scale(0.7)
```

SDXL:

```python
pipeline.load_ip_adapter(
    "h94/IP-Adapter-FaceID",
    subfolder=".",
    weight_name="ip-adapter-faceid_sdxl.bin",
    image_encoder_folder=None,
)
pipeline.set_ip_adapter_scale(0.7)
```

`set_ip_adapter_scale(0.7)` is a balanced default. Lower values such as `0.5` reduce FaceID influence. Higher values such as `0.8–1.0` increase similarity but may distort the scene.

### 9.3 Face Embedding Extraction

```python
import cv2
import torch
from insightface.app import FaceAnalysis


def extract_face_embeds(reference_image_path: str, device: str) -> torch.Tensor:
    providers = ["CUDAExecutionProvider"] if device == "cuda" else ["CPUExecutionProvider"]
    ctx_id = 0 if device == "cuda" else -1

    app = FaceAnalysis(name="buffalo_l", providers=providers)
    app.prepare(ctx_id=ctx_id, det_size=(640, 640))

    image = cv2.imread(reference_image_path)
    if image is None:
        raise ValueError(f"Could not read reference image: {reference_image_path}")

    faces = app.get(image)
    if not faces:
        raise ValueError(f"No face detected in reference image: {reference_image_path}")

    # Use the largest detected face by area.
    face = sorted(
        faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        reverse=True,
    )[0]
    return torch.from_numpy(face.normed_embedding).unsqueeze(0)
```

`buffalo_l` downloads automatically on first use to the InsightFace cache.

### 9.4 Face Detection Failure

If face detection fails, treat it as a recoverable scene-level fallback. Do not stop the whole job.

```python
try:
    face_embeds = extract_face_embeds(ref_path, device=plan.device)
except ValueError:
    logger.warning(
        "Face detection failed for %s. Falling back to prompt-only character hints.",
        character_name,
    )
    face_embeds = None
```

When `face_embeds` is `None`, omit `ip_adapter_image_embeds` from the Diffusers call.

### 9.5 Generation Call with FaceID Embeds

```python
import torch


def generate_image_with_faceid(
    pipeline,
    prompt_package: dict,
    face_embeds: "torch.Tensor | None",
) -> "PIL.Image.Image":
    generator = torch.Generator(device=pipeline.device.type).manual_seed(
        prompt_package["seed"]
    )
    call_kwargs = dict(
        prompt=prompt_package["positive_prompt"],
        negative_prompt=prompt_package["negative_prompt"],
        width=prompt_package["width"],
        height=prompt_package["height"],
        num_inference_steps=prompt_package["num_inference_steps"],
        guidance_scale=prompt_package["guidance_scale"],
        generator=generator,
    )
    if face_embeds is not None:
        call_kwargs["ip_adapter_image_embeds"] = [face_embeds]

    result = pipeline(**call_kwargs)
    if not result.images:
        raise RuntimeError("Diffusers returned no images.")
    return result.images[0]
```

Do not pass `ip_adapter_image_embeds=[None]`.

### 9.6 Multi-Character Scene Limitation

For MVP, FaceID should support **one primary character per scene by default** unless multi-character conditioning is explicitly tested with the chosen Diffusers version and model.

Recommended behavior:

1. If a scene has one main character and FaceID is enabled, use FaceID for that character.
2. If a scene has multiple characters, choose the primary character only if the prompt/scene metadata identifies one clearly.
3. Use prompt-based hints for the other characters.
4. Store the actual behavior in `outputs/manifest.json`.
5. Warn that multi-character identity consistency may be weaker.

Manifest example:

```json
{
  "character_consistency": {
    "method": "ip-adapter-faceid",
    "mode": "faceid_enabled",
    "enabled": true,
    "faceid_characters": ["Akira"],
    "prompt_only_characters": ["Hana"],
    "limitation": "Only the primary character used FaceID in this scene."
  }
}
```

Do not silently claim every character used FaceID if only one did.

### 9.7 Dependency Check

```python
# app/services/dependency_service.py
from dataclasses import dataclass


@dataclass(frozen=True)
class DependencyStatus:
    faceid_available: bool
    faceid_error: str | None = None


def check_generation_dependencies() -> DependencyStatus:
    return _check_faceid_imports()


def _check_faceid_imports() -> DependencyStatus:
    try:
        import insightface  # noqa: F401
        import onnxruntime  # noqa: F401
        import cv2  # noqa: F401
        return DependencyStatus(faceid_available=True)
    except ImportError as exc:
        return DependencyStatus(faceid_available=False, faceid_error=str(exc))
```

This check must be fast. Do not load InsightFace models during dependency checks.

---

## 10. PipelineFactory Pattern

`PipelineFactory` loads the correct pipeline, applies optimizations, attaches FaceID if enabled, and reuses the pipeline within one job.

```python
# app/services/pipeline_factory.py
import os
import torch
from diffusers import StableDiffusionXLPipeline, StableDiffusionPipeline

from app.core.errors import GlobalGenerationError
from app.schemas.generation import GenerationPlan, PipelineKind
from app.services.pipeline_factory_mock import MockPipeline


class PipelineFactory:
    def __init__(self):
        self._pipeline = None
        self._loaded_plan_key: str | None = None

    def load(self, plan: GenerationPlan):
        plan_key = f"{plan.pipeline}:{plan.model_id}:{plan.device}:{plan.faceid_enabled}"
        if self._pipeline is not None and self._loaded_plan_key == plan_key:
            return self._pipeline

        if os.getenv("USE_MOCK_PIPELINE", "false").lower() == "true":
            self._pipeline = MockPipeline(device=plan.device)
            self._loaded_plan_key = plan_key
            return self._pipeline

        try:
            if plan.pipeline == PipelineKind.sdxl:
                pipeline = self._load_sdxl(plan)
            else:
                pipeline = self._load_sd15(plan)

            if plan.faceid_enabled:
                self._attach_faceid(pipeline, plan)

            self._pipeline = pipeline
            self._loaded_plan_key = plan_key
            return self._pipeline
        except Exception as exc:
            self.unload()
            raise GlobalGenerationError(
                code="MODEL_LOAD_FAILED",
                message="The local image model could not be loaded. Check the model ID and installation.",
            ) from exc

    def unload(self) -> None:
        self._pipeline = None
        self._loaded_plan_key = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _load_sdxl(self, plan: GenerationPlan):
        try:
            pipeline = StableDiffusionXLPipeline.from_pretrained(
                plan.model_id,
                torch_dtype=torch.float16,
                use_safetensors=True,
                variant="fp16",
            )
        except Exception:
            pipeline = StableDiffusionXLPipeline.from_pretrained(
                plan.model_id,
                torch_dtype=torch.float16,
                use_safetensors=True,
            )
        pipeline = pipeline.to(plan.device)
        pipeline.enable_attention_slicing()
        pipeline.enable_vae_slicing()
        return pipeline

    def _load_sd15(self, plan: GenerationPlan):
        dtype = torch.float16 if plan.device == "cuda" else torch.float32
        pipeline = StableDiffusionPipeline.from_pretrained(
            plan.model_id,
            torch_dtype=dtype,
            use_safetensors=True,
        )
        pipeline = pipeline.to(plan.device)
        pipeline.enable_attention_slicing()
        return pipeline

    def _attach_faceid(self, pipeline, plan: GenerationPlan) -> None:
        weight_name = (
            "ip-adapter-faceid_sdxl.bin"
            if plan.pipeline == PipelineKind.sdxl
            else "ip-adapter-faceid_sd15.bin"
        )
        pipeline.load_ip_adapter(
            "h94/IP-Adapter-FaceID",
            subfolder=".",
            weight_name=weight_name,
            image_encoder_folder=None,
        )
        pipeline.set_ip_adapter_scale(0.7)
```

Call `factory.unload()` at the end of a generation job to free VRAM before the next job or app shutdown.

---

## 11. Per-Scene Status and Manifest Updates

Every approved scene must be recorded in both:

```text
metadata/generation_status.json
outputs/manifest.json
```

### 11.1 Required Per-Scene Update Flow

After each scene succeeds:

1. Save the image under `outputs/images/` with numeric prefix.
2. Append or update the manifest entry.
3. Mark the scene as generated in `generation_status.json`.
4. Store the seed, model ID, pipeline kind, output filename, and character consistency behavior.
5. Write a per-scene log line.
6. Atomically write JSON files.

After each scene fails recoverably:

1. Mark the scene as failed in `generation_status.json`.
2. Append or update the manifest entry with failure details.
3. Store error code and user-facing message.
4. Preserve already generated outputs.
5. Continue only if `continue_on_scene_failure=true`.

Global failures must stop the job and update project/job status.

### 11.2 Manifest Entry Shape

```json
{
  "scene_id": "scene_001",
  "scene_number": 1,
  "status": "generated",
  "output_file": "outputs/images/001_akira_enters_school.png",
  "seed": 92837412,
  "model_id": "stable-diffusion-v1-5/stable-diffusion-v1-5",
  "pipeline": "sd15",
  "width": 960,
  "height": 540,
  "character_consistency": {
    "method": "ip-adapter-faceid",
    "mode": "prompt_only",
    "enabled": false,
    "disabled_reason": "low_vram_default",
    "faceid_characters": [],
    "prompt_only_characters": ["Akira"]
  },
  "error": null
}
```

Failure example:

```json
{
  "scene_id": "scene_004",
  "scene_number": 4,
  "status": "failed",
  "output_file": null,
  "seed": 7238191,
  "model_id": "stabilityai/stable-diffusion-xl-base-1.0",
  "pipeline": "sdxl",
  "error": {
    "code": "CUDA_OUT_OF_MEMORY",
    "message": "Your GPU ran out of memory while generating scene 4. Try Low VRAM Preview or SD 1.5 fallback."
  }
}
```

---

## 12. Error-Code Mapping

Use consistent app errors. Never show raw exceptions in normal UI.

| Case | Error code | Scope | Behavior |
|---|---|---|---|
| Model cannot load | `MODEL_LOAD_FAILED` | Global | Stop job |
| CUDA OOM on first scene | `CUDA_OUT_OF_MEMORY` | Global | Stop job and suggest low-VRAM mode |
| CUDA OOM after first scene | `CUDA_OUT_OF_MEMORY` | Recoverable scene | Mark scene failed; continue if allowed |
| Diffusers returns no image | `SCENE_GENERATION_FAILED` | Recoverable scene | Mark scene failed |
| Reference file missing | `CHARACTER_REFERENCE_MISSING` | Readiness or scene | Block if required; otherwise prompt-only fallback if accepted |
| FaceID dependency missing | `FACEID_UNAVAILABLE` | Warning/fallback | Use prompt-only fallback if allowed |
| Face detection fails | `FACE_DETECTION_FAILED` | Scene warning/fallback | Use prompt-only for that character |
| Output image cannot save | `OUTPUT_SAVE_FAILED` | Recoverable or global | Mark scene failed; stop if filesystem broken |
| Manifest write fails | `MANIFEST_WRITE_FAILED` | Global | Stop job to avoid untracked outputs |
| Generation status write fails | `GENERATION_STATUS_WRITE_FAILED` | Global | Stop job to avoid misleading UI |
| Invalid generation plan | `GENERATION_PLAN_INVALID` | Global | Stop before model load |
| Job already running | `GENERATION_ALREADY_RUNNING` | Readiness | Block new job |
| Prompt missing/stale | `PROMPTS_MISSING` / `PROMPT_STALE` | Readiness | Block generation |
| Scenes not approved | `SCENE_APPROVAL_REQUIRED` | Readiness | Block generation |

---

## 13. Common Mistakes

| Mistake | Why it breaks | Correct approach |
|---|---|---|
| `runwayml/stable-diffusion-v1-5` | Archived repo, 404 on fresh download | Use `stable-diffusion-v1-5/stable-diffusion-v1-5` |
| Loading models at app startup | Slows startup, allocates VRAM immediately | Load inside `PipelineFactory.load()` only |
| `torch.float16` on CPU | Runtime errors | Use `torch.float32` when `device == "cpu"` |
| Passing `ip_adapter_image_embeds=[None]` | TypeError or silent wrong output | Omit argument when embeds are unavailable |
| Missing `image_encoder_folder=None` for FaceID | Diffusers tries to load CLIP encoder and fails | Always set `image_encoder_folder=None` |
| Catching all `Exception` around generation | Masks OOM and corrupts status handling | Catch `torch.cuda.OutOfMemoryError` separately |
| Batching scenes in one pipeline call | Spikes VRAM and breaks per-scene manifest | One scene per call |
| Skipping `enable_attention_slicing()` | Higher VRAM usage | Enable for all pipelines |
| Using CPU offload by default | Slow and state-prone for scene loops | Avoid unless manually tested |
| Not writing manifest after each scene | Output becomes untraceable | Atomically update manifest per scene |
| Claiming multi-character FaceID without testing | Misleading output metadata | Use one-primary-character FaceID or prompt-only fallback |

---

## 14. Windows-Specific Notes

### 14.1 InsightFace Installation

InsightFace has a C++ extension. On Windows, installation may require:

```text
Microsoft C++ Build Tools / Visual Studio Build Tools 2022
```

If `pip install insightface` fails, the setup script should print a warning and explain that FaceID will be unavailable. The app must not crash if InsightFace is missing.

### 14.2 ONNX Runtime Provider on Windows

On Windows with CUDA, use `onnxruntime-gpu`. On CPU-only Windows, use `onnxruntime`.

Do not install both in the same environment. `setup_windows_gpu.bat` should install `onnxruntime-gpu`; `setup_windows_cpu.bat` should install `onnxruntime`.

If the wrong provider is active, InsightFace may fall back to CPU. This is acceptable as long as the app records the actual behavior.

### 14.3 Model Download Location

HuggingFace Hub downloads models to:

```text
%USERPROFILE%\.cache\huggingface\hub
```

This can be changed with `HF_HOME`. The `.env.example` may document this for users with small system drives.

### 14.4 CUDA Cache Clearing

After a CUDA OOM, always call:

```python
torch.cuda.empty_cache()
```

This does not free memory held by an active pipeline, but it clears the allocator cache and helps reduce fragmentation between scenes.

### 14.5 File Path Safety

When passing reference image paths to `cv2.imread()`, always build the path through safe path helpers in `app/core/paths.py`. Never pass raw user-supplied filenames.

```python
# Good
ref_path = build_character_path(project_id, character.filename)
image = cv2.imread(str(ref_path))

# Bad
image = cv2.imread(character.filename)
```

---

## 15. Testing Without Real Models

All unit and integration tests must use `MockPipeline`. Set `USE_MOCK_PIPELINE=true` in the test environment.

```python
# conftest.py
import os
os.environ["USE_MOCK_PIPELINE"] = "true"
```

Or use pytest fixtures:

```python
import pytest


@pytest.fixture(autouse=True)
def mock_pipeline_env(monkeypatch):
    monkeypatch.setenv("USE_MOCK_PIPELINE", "true")
```

Tests must not:

- Download models from HuggingFace Hub.
- Require a CUDA GPU.
- Call `insightface.app.FaceAnalysis` with real models.
- Write huge image outputs.
- Depend on external internet access.

For InsightFace in tests, mock `extract_face_embeds` to return a fixed tensor:

```python
import torch
from unittest.mock import patch


def fake_face_embeds(path, device):
    return torch.zeros(1, 512)


with patch("app.services.generation_service.extract_face_embeds", fake_face_embeds):
    # run test
    ...
```

### 15.1 Minimum Tests for This Skill

Add tests for:

- `detect_hardware()` returns `cpu_only` when CUDA is unavailable.
- `detect_hardware()` returns `unknown` if detection raises unexpectedly.
- `select_generation_plan()` chooses SD 1.5 for `low_vram_4gb`.
- `select_generation_plan()` disables FaceID for `mid_vram_6_8gb` unless forced.
- `PipelineFactory` returns `MockPipeline` when `USE_MOCK_PIPELINE=true`.
- SD 1.5 loader uses `torch.float32` on CPU.
- FaceID embeds are omitted when face detection fails.
- Manifest is updated after success and recoverable failure.
- Global model load failure maps to `MODEL_LOAD_FAILED`.
- First-scene CUDA OOM maps to global `CUDA_OUT_OF_MEMORY`.
