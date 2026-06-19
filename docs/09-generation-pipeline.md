# 09 — Generation Pipeline

**Document:** `docs/09-generation-pipeline.md`  
**Product name:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Status:** Draft based on confirmed docs `00`–`08`  
**Primary user:** Non-technical anime/story creator  

---

## 1. Purpose

This document defines the Phase 1 local image generation pipeline for the Local AI Anime Storyboard Generator.

It is the implementation source of truth for how approved scenes and prompts become ordered anime storyboard images on the user's local machine.

This document covers:

- Generation readiness rules.
- Hardware detection and low-VRAM behavior.
- Diffusers pipeline selection.
- SDXL primary path.
- SD 1.5 low-VRAM fallback path.
- IP-Adapter-FaceID character consistency decision logic.
- Prompt-only fallback behavior.
- Per-scene generation execution.
- Output filename rules.
- `generation_settings.json` structure.
- `generation_status.json` structure.
- `outputs/manifest.json` structure.
- Retry and partial generation behavior.
- Error codes and logging expectations.

Phase 1 is **image-only**. Do not implement video generation, voice generation, lip-sync, subtitles, timeline export, cloud rendering, accounts, microservices, Celery, Redis, Kafka, or ComfyUI graph editing.

---

## 2. Source-of-Truth Constraints

The generation pipeline must obey these locked Phase 1 decisions:

1. The app runs locally on the user's machine.
2. The first supported OS is Windows.
3. The web app uses FastAPI, Jinja2, and HTMX.
4. Project data is stored as local folders and JSON files.
5. Image generation runs locally with Diffusers.
6. SDXL is the primary quality path when hardware allows.
7. SD 1.5 is the required fallback path for low-VRAM machines.
8. 4GB VRAM is a low-VRAM minimum target, not a guarantee that SDXL plus IP-Adapter-FaceID will run.
9. IP-Adapter-FaceID is the selected character consistency method when hardware and dependencies support it.
10. On 4GB VRAM machines, IP-Adapter-FaceID must be disabled by default.
11. When IP-Adapter-FaceID is disabled, use prompt-based character hints.
12. Character consistency is best effort and must not be described as perfect.
13. The user must review and approve scenes before prompts and image generation.
14. The backend must enforce generation state gates.
15. Generated images must preserve approved scene order with numeric filename prefixes.
16. Every generation result must be recorded in a local manifest.

---

## 3. Canonical Naming Rules

### 3.1 Character Consistency Method

Human-readable UI/developer docs name:

```text
IP-Adapter-FaceID
```

Persisted JSON/config/manifest value:

```text
ip-adapter-faceid
```

Do not use underscore variants such as:

```text
ip_adapter_faceid
```

### 3.2 Output Preset IDs

`docs/09-generation-pipeline.md` uses the canonical short preset IDs.

| Preset ID | Name | Width | Height | Aspect Ratio | Default Use |
|---|---|---:|---:|---|---|
| `youtube_standard` | YouTube Standard | 1280 | 720 | 16:9 | Default Phase 1 preset. |
| `youtube_high` | YouTube High | 1920 | 1080 | 16:9 | Higher quality, higher VRAM. |
| `low_vram_preview` | Low VRAM Preview | 960 | 540 | 16:9 | Recommended for 4GB VRAM. |
| `low_vram_tiny` | Low VRAM Tiny | 768 | 432 | 16:9 | Emergency fallback. |
| `square_preview` | Square Preview | 1024 | 1024 | 1:1 | Optional square output. |
| `vertical_short` | Vertical Short | 1080 | 1920 | 9:16 | Optional short-form output. |

Default preset:

```text
youtube_standard
```

### 3.3 Model IDs

Model IDs must be configurable through environment variables and persisted in generation metadata.

Recommended environment variables:

```env
IMAGE_MODEL_ID=stabilityai/stable-diffusion-xl-base-1.0
LOW_VRAM_IMAGE_MODEL_ID=stable-diffusion-v1-5/stable-diffusion-v1-5
```

The final anime-tuned SDXL model can be changed later without changing the pipeline contract.

---

## 4. Pipeline Position in the App Workflow

The generation pipeline starts only after the app has completed these earlier workflow steps:

```text
Create project
  ↓
Upload story.md
  ↓
Upload character references
  ↓
Split story into scenes with GPT
  ↓
User reviews and approves scenes
  ↓
Generate prompts
  ↓
Start local image generation
```

Disallowed flow:

```text
Story upload → GPT scene splitting → immediate image generation
```

The generation pipeline must never bypass scene review or prompt validation.

---

## 5. High-Level Generation Pipeline

```text
POST /projects/{project_id}/generation/start
  ↓
GenerationJobService.start_job()
  ↓
GenerationReadiness check
  ↓
HardwareService.detect_hardware()
  ↓
GenerationSettings resolved and saved
  ↓
GenerationService loads prompts and approved scenes
  ↓
Pipeline selection: SDXL / SD 1.5 / CPU fallback
  ↓
FaceID decision: enabled / disabled low-VRAM / unavailable / prompt-only
  ↓
For each approved scene:
      build final prompt package
      resolve character reference images
      generate image with Diffusers
      save image with numeric prefix
      update generation_status.json
      update outputs/manifest.json
      log success/failure
  ↓
Project status becomes GENERATION_COMPLETED, GENERATION_PARTIAL, or GENERATION_FAILED
```

---

## 6. Generation Inputs

### 6.1 Required Files

The generation pipeline requires these files:

```text
projects/{project_id}/metadata/project.json
projects/{project_id}/metadata/scenes.json
projects/{project_id}/metadata/prompts.json
projects/{project_id}/metadata/characters.json
projects/{project_id}/metadata/generation_settings.json
projects/{project_id}/outputs/images/
projects/{project_id}/outputs/manifest.json
projects/{project_id}/logs/generation.log
```

`outputs/manifest.json` may not exist before the first run. If missing, `ManifestService` must create it.

### 6.2 Required State

Generation may start only when:

```text
project.status = PROMPTS_GENERATED
```

or when retrying failed scenes from:

```text
project.status = GENERATION_PARTIAL
project.status = GENERATION_FAILED
```

Retry is allowed only if prompts are still valid and no generation job is running.

### 6.3 Required Scene Conditions

At least one active scene must exist with:

```text
status = approved
```

Skipped scenes must not be generated.

Deleted scenes must not be generated.

Generated scenes may be skipped during retry unless the user explicitly requests regeneration.

### 6.4 Required Prompt Conditions

Every active approved scene must have one prompt entry with:

```text
status = ready
```

Each prompt must include:

- `scene_id`
- `scene_number`
- `positive_prompt`
- `negative_prompt`
- `characters`
- `generation_settings`

Prompts marked `stale` must block generation.

---

## 7. Generation Readiness Gate

Before a job is created, `GenerationJobService` must run a readiness check.

### 7.1 Readiness Checklist

| Check | Required Behavior |
|---|---|
| Project exists | Return `PROJECT_NOT_FOUND` if missing. |
| No job running | Return `GENERATION_ALREADY_RUNNING` if another job is active. |
| Scenes exist | Return `SCENE_LIST_NOT_FOUND` if missing. |
| Scenes approved | Return `SCENE_APPROVAL_REQUIRED` if not approved. |
| Prompts exist | Return `PROMPTS_MISSING` if missing. |
| Prompts ready | Return `PROMPT_STALE` or `PROMPT_SCHEMA_INVALID` if invalid. |
| Characters valid | Return `CHARACTER_REFERENCE_MISSING` if required refs are missing. |
| Output folder writable | Return `OUTPUT_FOLDER_NOT_WRITABLE` if not writable. |
| Model config valid | Return `MODEL_CONFIG_INVALID` if model IDs are missing. |
| Hardware mode accepted | Return confirmation error if CPU or low-VRAM warning requires acknowledgement. |

### 7.2 Readiness Result Shape

Recommended internal model:

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "active_scene_count": 12,
  "prompt_count": 12,
  "warnings": [
    {
      "code": "LOW_VRAM_MODE_RECOMMENDED",
      "message": "Your GPU may not have enough VRAM for the selected preset. Low VRAM Preview is recommended."
    }
  ],
  "blocking_errors": []
}
```

If `blocking_errors` is not empty, generation must not start.

---

## 8. Hardware Detection

### 8.1 Detection Timing

Hardware detection should run:

1. When the generation page is opened.
2. Again immediately before generation starts.
3. When the user changes generation mode or preset.

Do not load SDXL during hardware detection.

### 8.2 Hardware Detection Output

Use PyTorch for first-pass detection.

Recommended internal shape:

```json
{
  "device": "cuda",
  "gpu_name": "NVIDIA GeForce RTX 3050 Laptop GPU",
  "vram_gb": 4.0,
  "cuda_available": true,
  "torch_dtype": "float16",
  "hardware_profile": "low_vram_4gb",
  "detected_at": "2026-06-11T10:15:30Z"
}
```

CPU-only shape:

```json
{
  "device": "cpu",
  "gpu_name": null,
  "vram_gb": 0,
  "cuda_available": false,
  "torch_dtype": "float32",
  "hardware_profile": "cpu_only",
  "detected_at": "2026-06-11T10:15:30Z"
}
```

### 8.3 Hardware Profiles

| Profile | Detection | Default Behavior |
|---|---|---|
| `cpu_only` | No CUDA GPU | CPU fallback only, show slow warning. |
| `low_vram_4gb` | CUDA GPU <= 4GB VRAM | SD 1.5 or low-res preset, FaceID off. |
| `mid_vram_6_8gb` | CUDA GPU >4GB and <=8GB | SDXL may run with optimizations, FaceID cautious. |
| `high_vram_12gb_plus` | CUDA GPU >=12GB | SDXL and FaceID are safer if dependencies work. |
| `unknown` | Detection failed | Use safe fallback and show warning. |

### 8.4 Low-VRAM Rule

4GB VRAM must always be treated as low-VRAM mode.

Default behavior for `low_vram_4gb`:

```text
Use SD 1.5 fallback or low-resolution preset.
Disable IP-Adapter-FaceID by default.
Use prompt-based character hints.
Show plain-language warning.
```

Do not silently attempt SDXL plus IP-Adapter-FaceID on 4GB VRAM.

---

## 9. Generation Modes

The UI may expose simple generation modes. Internally these modes control pipeline selection.

| Mode | Meaning | User-facing Availability |
|---|---|---|
| `auto` | App chooses based on hardware and preset. | Default. |
| `quality` | Prefer SDXL if hardware allows. | Optional. |
| `low_vram` | Prefer SD 1.5 fallback and low-res behavior. | Recommended for 4GB VRAM. |
| `cpu` | Force CPU fallback. | Only with warning. |

### 9.1 Default Mode

Default mode:

```text
auto
```

### 9.2 CPU Confirmation

If the app detects CPU-only mode, the UI should require explicit acknowledgement before starting generation.

Recommended form field:

```text
confirm_cpu_slow=true
```

Error if missing:

```text
CPU_GENERATION_CONFIRMATION_REQUIRED
```

### 9.3 Low-VRAM FaceID Confirmation

If selected settings disable IP-Adapter-FaceID, the UI may require acknowledgement.

Recommended form field:

```text
confirm_low_vram_faceid_disabled=true
```

This is optional for MVP. The UI may instead show a persistent warning and proceed.

---

## 10. Pipeline Selection

### 10.1 Selection Inputs

Pipeline selection uses:

- Hardware profile.
- Requested generation mode.
- Output preset.
- `IMAGE_MODEL_ID`.
- `LOW_VRAM_IMAGE_MODEL_ID`.
- `ENABLE_IP_ADAPTER_FACEID`.
- `FORCE_LOW_VRAM_MODE`.
- Prompt character references.
- Dependency health checks.

### 10.2 Selection Decision Table

| Hardware / Mode | Image Pipeline | Output Preset Recommendation | FaceID Default |
|---|---|---|---|
| `cpu_only` | SD 1.5 CPU fallback | `low_vram_preview` or `low_vram_tiny` | Disabled. |
| `low_vram_4gb` | SD 1.5 fallback | `low_vram_preview` | Disabled. |
| `mid_vram_6_8gb` | SDXL with optimizations or SD 1.5 fallback | `youtube_standard` cautiously | Disabled unless checks pass. |
| `high_vram_12gb_plus` | SDXL | `youtube_standard` or `youtube_high` | Enabled if dependencies pass. |
| `force_low_vram=true` | SD 1.5 fallback | `low_vram_preview` | Disabled. |

### 10.3 Pseudocode

```python
def select_generation_plan(settings, hardware, dependency_status):
    if settings.force_low_vram_mode:
        return GenerationPlan(
            pipeline="sd15",
            model_id=settings.low_vram_image_model_id,
            device=hardware.device,
            faceid_enabled=False,
            faceid_disabled_reason="force_low_vram_mode",
        )

    if settings.generation_mode == "cpu" or hardware.hardware_profile == "cpu_only":
        return GenerationPlan(
            pipeline="sd15",
            model_id=settings.low_vram_image_model_id,
            device="cpu",
            faceid_enabled=False,
            faceid_disabled_reason="cpu_mode",
        )

    if hardware.hardware_profile == "low_vram_4gb":
        return GenerationPlan(
            pipeline="sd15",
            model_id=settings.low_vram_image_model_id,
            device="cuda",
            faceid_enabled=False,
            faceid_disabled_reason="low_vram_default",
        )

    if hardware.hardware_profile == "mid_vram_6_8gb":
        faceid_enabled = (
            settings.enable_ip_adapter_faceid == "force"
            and dependency_status.faceid_available
        )
        return GenerationPlan(
            pipeline="sdxl",
            model_id=settings.image_model_id,
            device="cuda",
            faceid_enabled=faceid_enabled,
            faceid_disabled_reason=None if faceid_enabled else "mid_vram_cautious_default",
        )

    if hardware.hardware_profile == "high_vram_12gb_plus":
        faceid_enabled = (
            settings.enable_ip_adapter_faceid in ["auto", "true"]
            and dependency_status.faceid_available
        )
        return GenerationPlan(
            pipeline="sdxl",
            model_id=settings.image_model_id,
            device="cuda",
            faceid_enabled=faceid_enabled,
            faceid_disabled_reason=None if faceid_enabled else "faceid_unavailable",
        )

    return GenerationPlan(
        pipeline="sd15",
        model_id=settings.low_vram_image_model_id,
        device=hardware.device,
        faceid_enabled=False,
        faceid_disabled_reason="unknown_hardware_safe_fallback",
    )
```

---

## 11. Diffusers Pipeline Requirements

### 11.1 Model Loading

Models must be loaded lazily.

Do not load SDXL, SD 1.5, VAE, ControlNet, IP-Adapter, or FaceID dependencies at app startup.

Load generation models only when:

```text
Generation job starts
```

Reason:

- Faster app startup.
- Lower memory pressure.
- Easier troubleshooting.
- Avoids GPU allocation before the user needs generation.

### 11.2 Scene-by-Scene Execution

Generate scenes one at a time.

Do not batch multiple scenes in Phase 1.

Reasons:

- Lower VRAM pressure.
- Better progress reporting.
- Easier per-scene retry.
- Cleaner manifest updates.
- Safer partial output behavior.

### 11.3 Memory Optimizations

When using CUDA, the generation service should apply safe memory optimizations where supported:

- `torch.float16` for CUDA pipelines.
- Attention slicing if supported.
- VAE slicing if supported.
- CPU offload only if tested and useful.
- Clear CUDA cache after severe failures.

Do not enable experimental memory tricks that make output unreliable unless explicitly tested.

### 11.4 Unsupported Optimizations in MVP

Do not require these in Phase 1:

- xFormers as a hard dependency.
- TensorRT.
- ONNX conversion of diffusion models.
- Model quantization as the default path.
- Multi-GPU scheduling.
- Distributed generation.

These can be considered later, but the MVP must work without them.

---

## 12. Character Consistency Decision

### 12.1 FaceID Decision Inputs

For each generation job, decide whether IP-Adapter-FaceID can be used.

Inputs:

- Hardware profile.
- `ENABLE_IP_ADAPTER_FACEID` setting.
- `FORCE_LOW_VRAM_MODE` setting.
- IP-Adapter-FaceID weights availability.
- InsightFace availability.
- ONNX Runtime provider availability.
- Whether the scene has character references.
- Whether the selected pipeline supports the adapter integration.

### 12.2 Character Consistency Modes

| Mode | Persisted Value | Behavior |
|---|---|---|
| FaceID enabled | `faceid_enabled` | Use IP-Adapter-FaceID with character reference images. |
| Low-VRAM disabled | `faceid_disabled_low_vram` | Do not use FaceID; use prompt hints. |
| Dependency unavailable | `faceid_unavailable` | Show warning; use fallback if accepted. |
| Prompt-only | `prompt_only` | Use character names and same-outfit reminders only. |

### 12.3 Persisted Job Decision

Example stored in `generation_status.json` and manifest snapshots:

```json
{
  "character_consistency": {
    "method": "ip-adapter-faceid",
    "mode": "faceid_disabled_low_vram",
    "enabled": false,
    "disabled_reason": "low_vram_default",
    "fallback": "prompt_based_character_hints"
  }
}
```

### 12.4 Prompt-Based Character Fallback

When FaceID is disabled, the final prompt must still include character consistency hints.

Allowed fallback snippet:

```text
Akira, same outfit and visual identity as the uploaded reference image, anime style
```

Do not invent visual traits from the image unless a separate image-captioning step exists.

Bad fallback snippet if not explicitly provided by user or story:

```text
Akira, black messy hair, blue eyes, red jacket
```

Only include details that come from:

- The approved scene.
- The prompt metadata.
- User-provided character notes if added later.
- Reliable story context.

### 12.5 Multi-Character Scenes

Multi-character scenes are supported best effort.

If the selected FaceID implementation cannot reliably condition multiple characters at once:

- Continue with prompt-based hints for all characters.
- Optionally use FaceID only for the primary character if the implementation supports it safely.
- Store the actual behavior in manifest metadata.
- Warn that multi-character identity consistency may be weaker.

Do not silently claim every character used FaceID if only one did.

---

## 13. Generation Settings

### 13.1 File Path

Generation settings are stored at:

```text
projects/{project_id}/metadata/generation_settings.json
```

### 13.2 Generation Settings Schema

Recommended shape:

```json
{
  "version": 1,
  "project_id": "akira-episode-1-a7f3c2",
  "output_preset": {
    "id": "youtube_standard",
    "name": "YouTube Standard",
    "width": 1280,
    "height": 720,
    "aspect_ratio": "16:9"
  },
  "generation_mode": "auto",
  "image_model": {
    "primary_pipeline": "sdxl",
    "image_model_id": "stabilityai/stable-diffusion-xl-base-1.0",
    "low_vram_image_model_id": "runwayml/stable-diffusion-v1-5"
  },
  "defaults": {
    "num_images_per_scene": 1,
    "num_inference_steps": 30,
    "guidance_scale": 7.0,
    "seed_policy": "random_per_scene",
    "scheduler": "default",
    "negative_prompt": "low quality, blurry, pixelated, distorted face, asymmetrical eyes, bad anatomy, bad hands, extra fingers, missing fingers, duplicate character, inconsistent outfit, inconsistent hairstyle, text, subtitle, speech bubble, watermark, logo, cropped face, cropped body"
  },
  "hardware": {
    "device": "cuda",
    "gpu_name": "NVIDIA GeForce RTX 3050 Laptop GPU",
    "vram_gb": 4.0,
    "cuda_available": true,
    "torch_dtype": "float16",
    "hardware_profile": "low_vram_4gb",
    "detected_at": "2026-06-11T10:15:30Z"
  },
  "character_consistency": {
    "method": "ip-adapter-faceid",
    "enable_mode": "auto",
    "enabled": false,
    "disabled_reason": "low_vram_default",
    "fallback": "prompt_based_character_hints"
  },
  "safety": {
    "force_low_vram_mode": false,
    "continue_on_scene_failure": true,
    "overwrite_existing_outputs": false
  },
  "updated_at": "2026-06-11T10:15:30Z"
}
```

### 13.3 Required Numeric Defaults

Prompt metadata and generation settings must use explicit numeric defaults.

Balanced Phase 1 defaults:

```text
num_images_per_scene = 1
num_inference_steps = 30
guidance_scale = 7.0
```

Low-VRAM override may reduce `num_inference_steps`, but the chosen value must still be explicit.

### 13.4 Seed Policy

Allowed seed policies:

```text
random_per_scene
fixed_project_seed
manual_per_scene
```

Default:

```text
random_per_scene
```

If a seed is used for a generated image, store it in the manifest.

---

## 14. Prompt Package Construction

The prompt generation step creates `prompts.json`, but `GenerationService` is responsible for building the final runtime prompt package.

### 14.1 Runtime Prompt Package

For each scene, build:

```json
{
  "scene_id": "scene_001",
  "scene_number": 1,
  "positive_prompt": "...",
  "negative_prompt": "...",
  "width": 1280,
  "height": 720,
  "seed": 92837412,
  "num_inference_steps": 30,
  "guidance_scale": 7.0,
  "characters": [
    {
      "name": "Akira",
      "reference_image_path": "input/characters/Akira.png",
      "consistency_method": "ip-adapter-faceid",
      "runtime_consistency_mode": "prompt_only"
    }
  ]
}
```

### 14.2 Prompt Text Rules

Final prompt must include:

- Anime storyboard / anime illustration style.
- Scene summary visualized as a single image.
- Main visible action.
- Location.
- Mood.
- Camera shot and angle.
- Lighting.
- Character names.
- Outfit and visual identity reminders.
- Output aspect ratio implication through width/height settings.

Final prompt must avoid:

- Video terms.
- Timeline language.
- Lip-sync or voice instructions.
- Speech bubbles.
- Subtitles.
- Readable text in the image.
- Watermarks or logos.
- Contradictory camera instructions.

### 14.3 Negative Prompt Default

Default negative prompt:

```text
low quality, blurry, pixelated, distorted face, asymmetrical eyes, bad anatomy, bad hands, extra fingers, missing fingers, duplicate character, inconsistent outfit, inconsistent hairstyle, text, subtitle, speech bubble, watermark, logo, cropped face, cropped body
```

Users may edit negative prompts only through advanced prompt controls.

---

## 15. Per-Scene Generation Algorithm

### 15.1 Scene Execution Steps

For each active approved scene:

1. Load scene metadata from `metadata/scenes.json`.
2. Load matching prompt from `metadata/prompts.json`.
3. Resolve character reference paths from `metadata/characters.json`.
4. Build final runtime prompt package.
5. Decide runtime character consistency mode for the scene.
6. Load or reuse the selected Diffusers pipeline.
7. Apply IP-Adapter-FaceID inputs only if enabled and supported.
8. Generate one image by default.
9. Validate that an image object was returned.
10. Build output filename with numeric prefix.
11. Save image under `outputs/images/`.
12. Update `generation_status.json`.
13. Append or update `outputs/manifest.json`.
14. Write per-scene logs.
15. Continue to the next scene or stop depending on failure type.

### 15.2 Pseudocode

```python
def generate_project_images(project_id: str, job_id: str, target_scene_ids: list[str] | None = None):
    project = load_project(project_id)
    settings = load_generation_settings(project_id)
    scenes = load_approved_scenes(project_id)
    prompts = load_ready_prompts(project_id)
    characters = load_characters(project_id)

    if target_scene_ids:
        scenes = filter_scenes(scenes, target_scene_ids)

    hardware = hardware_service.detect_hardware()
    dependencies = dependency_service.check_generation_dependencies()
    plan = select_generation_plan(settings, hardware, dependencies)

    status = create_running_status(project_id, job_id, scenes, plan)
    manifest = manifest_service.load_or_create(project_id)

    pipeline = pipeline_factory.load(plan)

    for scene in scenes:
        if status.cancel_requested:
            mark_job_cancelled_after_current_scene()
            break

        try:
            update_current_scene(status, scene)
            prompt_package = build_prompt_package(scene, prompts, characters, settings, plan)
            image = pipeline.generate(prompt_package)
            output_asset = save_scene_image(project_id, scene, image, prompt_package, plan)
            manifest_service.record_success(manifest, output_asset)
            status_service.record_scene_success(status, output_asset)
        except RecoverableSceneGenerationError as exc:
            manifest_service.record_failure(manifest, scene, exc)
            status_service.record_scene_failure(status, scene, exc)
            if not settings.safety.continue_on_scene_failure:
                break
        except GlobalGenerationError as exc:
            status_service.record_global_failure(status, exc)
            manifest_service.record_global_failure(manifest, exc)
            break
        finally:
            safe_flush_status_and_manifest(status, manifest)

    finalize_project_generation_status(project, status, manifest)
```

---

## 16. Output Filename Rules

### 16.1 Required Folder

Generated images must be saved to:

```text
projects/{project_id}/outputs/images/
```

### 16.2 Filename Format

Required format:

```text
{scene_number:03d}_{scene_slug}.png
```

Examples:

```text
001_akira_enters_school.png
002_hana_warning.png
003_dark_hallway.png
```

### 16.3 Slug Rules

Scene slug must be derived from scene title or summary.

Rules:

- Lowercase.
- ASCII-safe if practical.
- Replace spaces with underscores.
- Remove unsafe path characters.
- Max recommended slug length: 60 characters.
- Never use user text directly as a path.
- If slug becomes empty, use `scene`.

### 16.4 Collision Handling

If the target filename already exists and overwrite is disabled:

```text
001_akira_enters_school.png
001_akira_enters_school_v2.png
001_akira_enters_school_v3.png
```

Default:

```text
overwrite_existing_outputs = false
```

### 16.5 Ordering Rule

The numeric prefix must reflect approved scene order at generation time.

If scenes are reordered after an earlier generation, new generation outputs must use the new order and old outputs should remain in place unless a regeneration cleanup feature is explicitly added.

---

## 17. Generation Status

### 17.1 File Path

Runtime job status is stored at:

```text
projects/{project_id}/metadata/generation_status.json
```

### 17.2 Job Status Values

Allowed values:

```text
queued
running
completed
partial
failed
cancel_requested
cancelled
```

### 17.3 Status Schema

Recommended shape:

```json
{
  "version": 1,
  "project_id": "akira-episode-1-a7f3c2",
  "job_id": "gen_20260611_101530",
  "status": "running",
  "started_at": "2026-06-11T10:15:30Z",
  "updated_at": "2026-06-11T10:18:00Z",
  "completed_at": null,
  "generation_plan": {
    "pipeline": "sd15",
    "model_id": "runwayml/stable-diffusion-v1-5",
    "device": "cuda",
    "torch_dtype": "float16",
    "output_preset_id": "low_vram_preview"
  },
  "character_consistency": {
    "method": "ip-adapter-faceid",
    "mode": "faceid_disabled_low_vram",
    "enabled": false,
    "disabled_reason": "low_vram_default",
    "fallback": "prompt_based_character_hints"
  },
  "total_scenes": 12,
  "completed_scenes": 4,
  "failed_scenes": 0,
  "skipped_scenes": 0,
  "current_scene_id": "scene_005",
  "current_scene_number": 5,
  "current_scene_title": "The dark hallway",
  "progress_percent": 33,
  "current_message": "Generating scene 5 of 12",
  "scene_results": [
    {
      "scene_id": "scene_001",
      "scene_number": 1,
      "status": "success",
      "output_path": "outputs/images/001_akira_enters_school.png",
      "error_code": null,
      "error_message": null,
      "started_at": "2026-06-11T10:15:40Z",
      "completed_at": "2026-06-11T10:16:20Z"
    }
  ],
  "errors": []
}
```

### 17.4 Status Update Rule

`generation_status.json` must be updated after each scene succeeds or fails.

Use atomic JSON writes.

Do not wait until the full job completes to write status.

Reason:

- HTMX polling needs progress.
- Partial results must survive app crashes.
- Retry needs accurate failed scene state.

---

## 18. Output Manifest

### 18.1 File Path

Output manifest path:

```text
projects/{project_id}/outputs/manifest.json
```

### 18.2 Manifest Purpose

The manifest maps generated files back to:

- Project.
- Generation job.
- Scene.
- Prompt.
- Character references.
- Model and settings.
- Success or failure state.

### 18.3 Manifest Schema

Recommended shape:

```json
{
  "version": 1,
  "project_id": "akira-episode-1-a7f3c2",
  "latest_job_id": "gen_20260611_101530",
  "created_at": "2026-06-11T10:15:30Z",
  "updated_at": "2026-06-11T10:25:10Z",
  "assets": [
    {
      "asset_id": "asset_scene_001_gen_20260611_101530",
      "job_id": "gen_20260611_101530",
      "scene_id": "scene_001",
      "scene_number": 1,
      "scene_title": "Akira enters the school",
      "prompt_id": "scene_001",
      "output_filename": "001_akira_enters_school.png",
      "output_path": "outputs/images/001_akira_enters_school.png",
      "width": 1280,
      "height": 720,
      "status": "success",
      "image_model_id": "stabilityai/stable-diffusion-xl-base-1.0",
      "pipeline": "sdxl",
      "seed": 92837412,
      "num_inference_steps": 30,
      "guidance_scale": 7.0,
      "output_preset_id": "youtube_standard",
      "character_references": [
        {
          "name": "Akira",
          "reference_image_path": "input/characters/Akira.png",
          "consistency_method": "ip-adapter-faceid",
          "runtime_consistency_mode": "faceid_enabled"
        }
      ],
      "positive_prompt_hash": "sha256:...",
      "negative_prompt_hash": "sha256:...",
      "created_at": "2026-06-11T10:16:20Z",
      "error_code": null,
      "error_message": null
    }
  ]
}
```

### 18.4 Failure Asset Entry

If a scene fails, record a manifest entry with `status = failed`.

```json
{
  "asset_id": "asset_scene_004_gen_20260611_101530",
  "job_id": "gen_20260611_101530",
  "scene_id": "scene_004",
  "scene_number": 4,
  "scene_title": "The mirror breaks",
  "prompt_id": "scene_004",
  "output_filename": null,
  "output_path": null,
  "width": 1280,
  "height": 720,
  "status": "failed",
  "image_model_id": "stabilityai/stable-diffusion-xl-base-1.0",
  "pipeline": "sdxl",
  "seed": 5512882,
  "error_code": "CUDA_OUT_OF_MEMORY",
  "error_message": "The GPU ran out of memory while generating this scene.",
  "created_at": "2026-06-11T10:20:00Z"
}
```

### 18.5 Prompt Hashing

Do not store full prompt text in the manifest unless explicitly needed.

Recommended:

- Store prompt text in `metadata/prompts.json`.
- Store prompt hashes in manifest.
- Store prompt ID / scene ID to link manifest back to prompt metadata.

This keeps the manifest compact while preserving traceability.

---

## 19. Job Concurrency

### 19.1 Single Job Rule

Only one generation job may run at a time per local app process.

If a job is already running, return:

```text
GENERATION_ALREADY_RUNNING
```

### 19.2 Recommended Runner

Use:

```text
ThreadPoolExecutor(max_workers=1)
```

This keeps the app simple and avoids external queues.

Do not add Celery, Redis, RabbitMQ, Kafka, or background worker services in Phase 1.

### 19.3 Job ID Format

Recommended format:

```text
gen_YYYYMMDD_HHMMSS
```

Example:

```text
gen_20260611_101530
```

If multiple jobs start within the same second, append a short suffix:

```text
gen_20260611_101530_a7f3
```

---

## 20. Failure Handling

### 20.1 Scene-Level Recoverable Failures

Examples:

- One prompt causes generation error.
- One character reference cannot be used for FaceID.
- One output file save fails.
- One scene hits an image validation issue.

Default behavior:

```text
Mark scene failed.
Log error.
Update status and manifest.
Continue remaining scenes when safe.
```

### 20.2 Global Failures

Examples:

- Model cannot load.
- CUDA is unavailable after pipeline selected CUDA.
- Output folder is not writable.
- Required dependency is missing and no fallback is accepted.
- Repeated CUDA out-of-memory on first scene.

Default behavior:

```text
Stop job.
Mark job failed.
Keep completed outputs.
Show clear error.
```

### 20.3 CUDA Out-of-Memory Behavior

If CUDA OOM happens:

1. Mark current scene as failed.
2. Log technical details to `generation.log`.
3. Show plain-language UI message.
4. Try to clear CUDA cache if safe.
5. If OOM happens on the first scene, stop the job and recommend Low VRAM Preview or SD 1.5 fallback.
6. If OOM happens after several successful scenes, stop or continue based on safety setting.

User-facing message:

```text
Your GPU ran out of memory while generating this scene. Try Low VRAM Preview or SD 1.5 fallback.
```

Do not show raw stack traces in the UI.

---

## 21. Retry Behavior

### 21.1 Retry Failed Scenes

The app should support retrying failed scenes if feasible in Phase 1.

Route:

```text
POST /projects/{project_id}/generation/retry-failed
```

Retry target:

```text
Scenes with status = failed in generation_status.json or manifest.json
```

### 21.2 Retry Preconditions

Retry is allowed only when:

- No job is running.
- Failed scenes exist.
- Scenes are still approved.
- Prompts are still ready.
- Character references still exist.
- Output folder is writable.

### 21.3 Retry Output Filenames

Retry must not overwrite earlier failed manifest entries.

If retry succeeds, create a new success asset entry with the new job ID.

If output filename collides, use `_v2`, `_v3`, etc.

### 21.4 Regenerate All Scenes

Full regeneration can be added later.

If implemented, require explicit confirmation because it may create duplicate outputs or overwrite previous runs depending on settings.

Default MVP behavior:

```text
Retry failed scenes only.
Do not delete previous successful outputs.
```

---

## 22. Cancellation

Cancellation is optional for the first MVP.

If implemented:

1. User clicks cancel.
2. App sets `status = cancel_requested` in `generation_status.json`.
3. Generation thread checks cancellation flag between scenes.
4. Current scene may finish or fail safely.
5. Remaining scenes are not generated.
6. Job becomes `cancelled`.
7. Existing outputs remain.
8. Manifest remains valid.

If not implemented, route must return:

```text
GENERATION_CANCEL_NOT_SUPPORTED
```

Do not kill the Python process to cancel generation.

---

## 23. Logging

### 23.1 Log Files

Global app log:

```text
logs/app.log
```

Project generation log:

```text
projects/{project_id}/logs/generation.log
```

### 23.2 Required Generation Logs

Log these events:

- Generation job created.
- Generation readiness result.
- Hardware profile.
- Selected pipeline.
- Model IDs.
- Output preset.
- FaceID enabled/disabled decision.
- Dependency health check result.
- Scene generation start.
- Scene generation success.
- Scene generation failure.
- Output filename.
- Manifest update.
- Job final status.

### 23.3 Do Not Log

Do not log:

- OpenAI API key.
- Full raw story content repeatedly.
- Image binary data.
- Large base64 strings.
- Full absolute local paths unless debug mode is enabled.
- Raw stack traces in user-facing responses.

Technical stack traces may be logged in `generation.log` when useful.

---

## 24. Error Codes

### 24.1 Readiness Errors

| Code | Meaning |
|---|---|
| `GENERATION_NOT_READY` | Generic readiness failure. |
| `SCENE_APPROVAL_REQUIRED` | Scenes are not approved. |
| `SCENE_LIST_NOT_FOUND` | Scene metadata missing. |
| `PROMPTS_MISSING` | Prompt metadata missing. |
| `PROMPT_STALE` | Prompt no longer matches approved scene/settings. |
| `PROMPT_SCHEMA_INVALID` | Prompt metadata failed validation. |
| `CHARACTER_REFERENCE_MISSING` | Required character reference missing. |
| `OUTPUT_FOLDER_NOT_WRITABLE` | Cannot write output image folder. |
| `MODEL_CONFIG_INVALID` | Model config missing or invalid. |
| `GENERATION_ALREADY_RUNNING` | Another job is active. |
| `CPU_GENERATION_CONFIRMATION_REQUIRED` | CPU mode needs user acknowledgement. |

### 24.2 Runtime Errors

| Code | Meaning |
|---|---|
| `MODEL_LOAD_FAILED` | Diffusers model could not load. |
| `MODEL_DEPENDENCY_MISSING` | Required package or weight missing. |
| `CUDA_UNAVAILABLE` | CUDA selected but unavailable. |
| `CUDA_OUT_OF_MEMORY` | GPU memory exhausted. |
| `FACEID_DEPENDENCY_MISSING` | FaceID dependency unavailable. |
| `FACEID_REFERENCE_INVALID` | Character reference unsuitable for FaceID runtime. |
| `SCENE_GENERATION_FAILED` | One scene failed for generic reason. |
| `IMAGE_SAVE_FAILED` | Generated image could not be saved. |
| `MANIFEST_WRITE_FAILED` | Manifest update failed. |
| `GENERATION_STATUS_WRITE_FAILED` | Status update failed. |
| `GENERATION_CANCEL_NOT_SUPPORTED` | Cancellation not implemented. |
| `NO_FAILED_SCENES_TO_RETRY` | Retry requested but no failed scenes exist. |

### 24.3 User-Facing Error Rule

Every error must map to a plain-language message.

Bad:

```text
RuntimeError: mat1 and mat2 shapes cannot be multiplied
```

Good:

```text
Image generation failed for this scene. Try regenerating it or switching to Low VRAM Preview.
```

---

## 25. Service Responsibilities

### 25.1 `HardwareService`

Responsibilities:

- Detect CPU/GPU.
- Detect CUDA availability.
- Estimate VRAM.
- Assign hardware profile.
- Save hardware snapshot to `generation_settings.json`.
- Produce user-facing warnings.

### 25.2 `GenerationJobService`

Responsibilities:

- Enforce single-job rule.
- Run readiness checks.
- Create job ID.
- Initialize `generation_status.json`.
- Start background generation with `ThreadPoolExecutor(max_workers=1)`.
- Expose job status for polling.
- Handle retry failed scenes.
- Handle cancellation if implemented.

### 25.3 `GenerationService`

Responsibilities:

- Load scenes, prompts, characters, and settings.
- Select generation plan.
- Load Diffusers pipeline lazily.
- Build runtime prompt packages.
- Resolve character references.
- Apply FaceID only when enabled and safe.
- Run image generation scene by scene.
- Save generated images.
- Update status and manifest.
- Log results.

### 25.4 `ManifestService`

Responsibilities:

- Load or create `outputs/manifest.json`.
- Record successful assets.
- Record failed scene attempts.
- Store job/model/settings snapshots.
- Preserve old outputs and old manifest entries.
- Write manifest atomically.

### 25.5 `PipelineFactory`

Recommended helper owned by `GenerationService` or a separate module.

Responsibilities:

- Load SDXL pipeline.
- Load SD 1.5 pipeline.
- Configure device and dtype.
- Apply memory optimizations.
- Attach FaceID components if enabled.
- Reuse loaded pipeline inside a job.

#### 25.5.1 IP-Adapter-FaceID Weight Files

HuggingFace repo:

```text
h94/IP-Adapter-FaceID
```

Weight file by pipeline:

| Pipeline | Weight file |
|---|---|
| SD 1.5 | `ip-adapter-faceid_sd15.bin` |
| SDXL | `ip-adapter-faceid_sdxl.bin` |

#### 25.5.2 Loading IP-Adapter-FaceID onto a Pipeline

Call `load_ip_adapter` after the base pipeline is loaded.

SD 1.5 example:

```python
pipeline.load_ip_adapter(
    "h94/IP-Adapter-FaceID",
    subfolder=".",
    weight_name="ip-adapter-faceid_sd15.bin",
    image_encoder_folder=None,
)
pipeline.set_ip_adapter_scale(0.7)
```

SDXL example:

```python
pipeline.load_ip_adapter(
    "h94/IP-Adapter-FaceID",
    subfolder=".",
    weight_name="ip-adapter-faceid_sdxl.bin",
    image_encoder_folder=None,
)
pipeline.set_ip_adapter_scale(0.7)
```

`image_encoder_folder=None` is required because IP-Adapter-FaceID uses InsightFace embeddings, not a CLIP image encoder.

#### 25.5.3 Face Embedding Extraction

Extract face embeddings from the character reference image using InsightFace before calling the pipeline.

```python
import cv2
import torch
from insightface.app import FaceAnalysis

def extract_face_embeds(reference_image_path: str, device: str) -> torch.Tensor:
    providers = ["CUDAExecutionProvider"] if device == "cuda" else ["CPUExecutionProvider"]
    app = FaceAnalysis(name="buffalo_l", providers=providers)
    app.prepare(ctx_id=0, det_size=(640, 640))

    image = cv2.imread(reference_image_path)
    faces = app.get(image)

    if not faces:
        raise ValueError(f"No face detected in reference image: {reference_image_path}")

    # Use the largest detected face
    face = sorted(faces, key=lambda f: f.bbox[2] - f.bbox[0], reverse=True)[0]
    return torch.from_numpy(face.normed_embedding).unsqueeze(0)
```

`buffalo_l` is the recommended InsightFace model for quality face analysis. It downloads automatically on first use.

#### 25.5.4 Generation Call with FaceID Embeds

Pass the extracted embedding as `ip_adapter_image_embeds`:

```python
face_embeds = extract_face_embeds(reference_image_path, device=plan.device)

image = pipeline(
    prompt=positive_prompt,
    negative_prompt=negative_prompt,
    ip_adapter_image_embeds=[face_embeds],
    width=prompt_package.width,
    height=prompt_package.height,
    num_inference_steps=prompt_package.num_inference_steps,
    guidance_scale=prompt_package.guidance_scale,
    generator=torch.Generator(device=plan.device).manual_seed(prompt_package.seed),
).images[0]
```

If the scene has no character reference or face detection fails, fall back to `prompt_only` mode and log a warning. Do not raise a `GlobalGenerationError` for a missing face — it is a recoverable per-scene condition.

---

## 26. Suggested Module Layout

Recommended files:

```text
app/services/generation_service.py
app/services/generation_job_service.py
app/services/hardware_service.py
app/services/manifest_service.py
app/services/pipeline_factory.py
app/schemas/generation.py
app/schemas/jobs.py
app/schemas/manifest.py
```

Optional helper modules:

```text
app/services/faceid_service.py
app/services/prompt_package_service.py
app/core/image_io.py
app/core/slugify.py
```

Do not create a separate microservice or worker process in Phase 1.

---

## 27. Schema Models

### 27.1 Recommended Enums

```python
class GenerationMode(str, Enum):
    auto = "auto"
    quality = "quality"
    low_vram = "low_vram"
    cpu = "cpu"

class HardwareProfile(str, Enum):
    cpu_only = "cpu_only"
    low_vram_4gb = "low_vram_4gb"
    mid_vram_6_8gb = "mid_vram_6_8gb"
    high_vram_12gb_plus = "high_vram_12gb_plus"
    unknown = "unknown"

class GenerationJobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    partial = "partial"
    failed = "failed"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"

class PipelineKind(str, Enum):
    sdxl = "sdxl"
    sd15 = "sd15"

class CharacterConsistencyMode(str, Enum):
    faceid_enabled = "faceid_enabled"
    faceid_disabled_low_vram = "faceid_disabled_low_vram"
    faceid_unavailable = "faceid_unavailable"
    prompt_only = "prompt_only"
```

### 27.2 Output Preset Model

```python
class OutputPreset(BaseModel):
    id: str
    name: str
    width: int
    height: int
    aspect_ratio: str
```

Allowed IDs are the canonical short IDs from Section 3.2.

### 27.3 Generation Plan Model

```python
class GenerationPlan(BaseModel):
    pipeline: PipelineKind
    model_id: str
    device: str
    torch_dtype: str
    output_preset_id: str
    faceid_enabled: bool
    faceid_disabled_reason: str | None = None
```

---

## 28. UI Requirements

### 28.1 Generation Page

The generation page should show:

- Readiness status.
- Selected output preset.
- Hardware profile.
- Character consistency status.
- Low-VRAM warning if relevant.
- CPU slow warning if relevant.
- Start generation button when ready.
- Current job progress if running.
- Retry failed scenes button if partial.

### 28.2 Progress Partial

HTMX polling route:

```text
GET /projects/{project_id}/generation/status
```

The progress UI should show:

- Current scene number.
- Total scenes.
- Current scene title.
- Progress percentage.
- Successful scenes count.
- Failed scenes count.
- Latest generated preview if available.
- Plain-language current message.

### 28.3 Low-VRAM Copy

Recommended user-facing warning:

```text
Your GPU may not have enough memory for the full-quality setup. The app will use a lighter generation mode and character consistency will rely on prompt hints.
```

Avoid showing this in the default flow:

```text
IP-Adapter-FaceID disabled because ONNX Runtime provider failed and CUDA allocator fragmentation caused OOM.
```

Technical details belong in logs or advanced settings.

---

## 29. Security and File Safety

### 29.1 Path Safety

Rules:

- Never trust scene titles as file paths.
- Never trust character filenames as paths.
- Store project-relative paths in metadata.
- Build absolute paths only through safe path helpers.
- Reject path traversal.
- Write only under `projects/{project_id}/`.

### 29.2 Localhost Scope

Generation routes are local-only and must not require hosted authentication.

The app must bind to:

```text
127.0.0.1
```

by default.

### 29.3 No Remote Rendering

Do not upload character images, generated images, or local model inputs to a cloud renderer in Phase 1.

OpenAI is used for story and prompt text only, before the generation pipeline.

---

## 30. Testing Requirements

### 30.1 Unit Tests

Recommended unit tests:

- Hardware profile classification.
- Output preset lookup.
- Generation plan selection.
- FaceID enabled/disabled decision.
- Prompt package building.
- Filename slug creation.
- Manifest success entry creation.
- Manifest failure entry creation.
- Status progress calculation.
- Readiness gate errors.

### 30.2 Integration Tests with Mocked Diffusers

Use a fake pipeline that returns a small generated image object.

Test:

1. Project with approved scenes and ready prompts starts generation.
2. Job status becomes running.
3. Fake image is saved to `outputs/images/`.
4. Manifest is updated.
5. Project status becomes `GENERATION_COMPLETED`.
6. Failed fake scene produces `GENERATION_PARTIAL`.
7. Retry failed scenes only regenerates failed scene IDs.

### 30.3 Tests Not Required for MVP

Do not require automated tests that actually download SDXL or run full GPU generation in CI.

Heavy AI tests should be manual or opt-in local tests.

---

## 31. Acceptance Criteria

The generation pipeline is complete for Phase 1 when:

1. Generation cannot start before scene approval.
2. Generation cannot start before prompts are ready.
3. Hardware detection classifies CPU, 4GB low-VRAM, mid-VRAM, and high-VRAM profiles.
4. 4GB VRAM defaults to low-VRAM behavior.
5. IP-Adapter-FaceID is disabled by default on 4GB VRAM.
6. Prompt-based character hints are used when FaceID is disabled.
7. SDXL path is configurable by `IMAGE_MODEL_ID`.
8. SD 1.5 fallback path is configurable by `LOW_VRAM_IMAGE_MODEL_ID`.
9. The app generates one image per approved scene by default.
10. Images are generated scene by scene, not batched.
11. Generated images are saved under `outputs/images/`.
12. Image filenames use numeric scene prefixes.
13. `generation_status.json` is updated after each scene.
14. `outputs/manifest.json` records every success and failure.
15. Completed outputs are preserved when later scenes fail.
16. A partial generation can be reviewed by the user.
17. Failed scenes can be retried if retry is implemented.
18. Raw stack traces are not shown in the UI.
19. Logs contain enough detail to debug model, hardware, FaceID, and per-scene failures.
20. No video generation, cloud rendering, queue broker, account system, or microservice is introduced.

---

## 32. Implementation Notes for Codex Agent

When implementing this document:

1. Start with schemas and JSON file read/write behavior.
2. Implement readiness checks before touching Diffusers.
3. Implement mocked generation first.
4. Save fake images and manifest entries in tests.
5. Add hardware detection.
6. Add SD 1.5 fallback loading.
7. Add SDXL loading.
8. Add FaceID dependency checks last.
9. Keep FaceID optional and hardware-conditional.
10. Do not let a FaceID setup failure break prompt-only fallback unless the user explicitly requires FaceID.
11. Keep user-facing messages simple.
12. Keep technical details in logs.

Recommended implementation order:

```text
schemas → manifest service → status service → readiness gate → fake pipeline → real SD 1.5 → real SDXL → FaceID dependency check → FaceID integration
```

---

## 33. Guardrails

Codex Agent must not violate these rules:

1. Do not implement video generation.
2. Do not implement cloud rendering.
3. Do not add React or a frontend build pipeline.
4. Do not add Celery, Redis, Kafka, or external queues.
5. Do not add a database.
6. Do not start generation before scene approval.
7. Do not skip prompt validation.
8. Do not promise perfect character consistency.
9. Do not enable IP-Adapter-FaceID by default on 4GB VRAM.
10. Do not silently ignore missing character references.
11. Do not overwrite generated outputs by default.
12. Do not store API keys in project metadata, manifest, prompts, or logs.
13. Do not use underscore-based `ip_adapter_faceid` in persisted JSON.
14. Do not use legacy long output preset IDs in new generation metadata.

---

## 34. Open Questions Not Blocking MVP

These can be decided later without changing the core pipeline contract:

1. Final anime-tuned SDXL model ID.
2. Whether SDXL should be attempted on 6GB VRAM by default or only with user confirmation.
3. Whether prompt-only fallback should always continue or require explicit user acknowledgement.
4. Whether to support multiple images per scene in the first implementation.
5. Whether to add image upscaling after low-VRAM generation.
6. Whether to keep every generation run in separate output subfolders later.
7. Whether to add preview thumbnails separate from full output images.
8. Whether cancellation should be implemented in the first MVP or after retry support.

---

## 35. Final Phase 1 Position

The generation pipeline is a local, simple, scene-by-scene Diffusers image generation flow.

It should feel simple to the user:

```text
Review scenes → Generate images → Open ordered output folder
```

Internally, it must be strict about:

```text
readiness gates → hardware-safe pipeline choice → best-effort character consistency → ordered files → manifest traceability
```
