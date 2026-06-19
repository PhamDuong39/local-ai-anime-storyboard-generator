# Local AI Anime Storyboard Generator — Tech Stack

**Document:** `docs/06-techstack.md`  
**Product name:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Status:** Draft based on confirmed product decisions and verified package/model identifiers  
**Primary user:** Non-technical anime/story creator  
**Last verified:** 2026-06-10

---

## 1. Purpose

This document defines the implementation tech stack for Phase 1 of the Local AI Anime Storyboard Generator.

It is intended to give Codex Agent, or another coding agent, enough concrete technical direction to build the MVP without making major stack decisions independently.

This document covers:

- Runtime language and Python version.
- Local web app stack.
- OpenAI API client and model identifiers.
- Local image generation stack.
- Character consistency dependencies.
- Low-VRAM fallback strategy.
- Local storage approach.
- Windows-first setup strategy.
- Development tooling.
- Explicitly forbidden technologies for Phase 1.

Phase 1 is **image-only**. Do not add video generation, voice generation, lip-sync, subtitle generation, cloud rendering, hosted accounts, React, microservices, or message brokers.

---

## 2. Source-of-Truth Product Constraints

The tech stack must respect these locked decisions:

1. The app is a local AI anime storyboard/image generator.
2. Phase 1 generates ordered images only.
3. The app runs locally on the user's machine.
4. First supported OS is Windows.
5. The local web UI uses FastAPI + Jinja2 + HTMX.
6. The user uploads one free-form Markdown story file.
7. The user uploads one full-body reference image per main character.
8. GPT is used for scene splitting and prompt generation.
9. The user must review and approve scenes before image generation.
10. Local image generation uses Diffusers + SDXL as the primary direction.
11. SD 1.5 fallback must exist as the low-VRAM safety path.
12. Character consistency uses IP-Adapter-FaceID when hardware supports it.
13. On 4GB VRAM machines, IP-Adapter-FaceID must be disabled by default unless hardware detection confirms it can run safely.
14. Generated images must preserve story order using numeric filename prefixes.
15. Project files are stored locally in structured folders.

---

## 3. Stack Summary

| Area | Phase 1 Choice | Notes |
|---|---|---|
| Language | Python | Single-language MVP to reduce complexity. |
| Python version | Python 3.12.x | Recommended for Windows + AI package compatibility. |
| Backend | FastAPI | Local HTTP app at `localhost`. |
| ASGI server | Uvicorn | Development and local runtime server. |
| HTML templates | Jinja2 | Server-rendered UI. |
| UI interactivity | HTMX | Avoid React and heavy frontend build tooling. |
| CSS | Plain CSS or lightweight local CSS file | No Tailwind build pipeline required in Phase 1. |
| Validation models | Pydantic v2 | Strict scene/prompt/project schemas. |
| OpenAI SDK | `openai` Python SDK | Used for scene splitting and prompt generation. |
| Scene model | `gpt-5.4-mini` | Verified API-style identifier for product decision `gpt 5.4 mini`. |
| Image generation | PyTorch + Diffusers | Local generation pipeline. |
| Main image model direction | SDXL | Default quality path when hardware allows. |
| Low-VRAM fallback | SD 1.5 | Required fallback for 4GB VRAM / weak GPUs. |
| Character consistency | IP-Adapter-FaceID | Enabled only when dependencies and hardware allow. |
| Image loading | Pillow | Story/character image validation and metadata. |
| Local metadata storage | JSON files | No database required for Phase 1. |
| Logs | Python logging | Write to local project logs and app logs. |
| Packaging MVP | Windows `.bat` scripts | Full installer can come later. |
| Containerization | Not required | Do not make Docker the only workflow. |

---

## 4. Runtime Baseline

### 4.1 Python Version

Recommended runtime:

```text
Python 3.12.x 64-bit
```

Reason:

- Works well with FastAPI, Pydantic, Jinja2, and current AI packages.
- Avoids unnecessary risk from very new Python versions where binary AI wheels may lag.
- Keeps Windows setup less painful for non-technical users.

Do not target Python 3.14 or free-threaded Python builds for Phase 1.

### 4.2 Operating System

Primary OS:

```text
Windows 10 / Windows 11, 64-bit
```

Development may happen on Linux or macOS, but setup scripts, local paths, and user instructions must be Windows-first.

### 4.3 GPU Runtime

Primary supported GPU path:

```text
NVIDIA GPU + CUDA-enabled PyTorch wheel
```

CPU fallback may exist, but it is expected to be very slow and should be shown as a fallback mode, not the recommended path.

---

## 5. Backend Stack

### 5.1 FastAPI

Use FastAPI for all local backend routes.

Recommended version policy:

```text
fastapi>=0.136,<0.137
```

Responsibilities:

- Serve local web UI.
- Handle story upload.
- Handle character reference upload.
- Manage project metadata files.
- Call OpenAI for scene splitting and prompt generation.
- Start local generation jobs.
- Stream or poll generation progress.
- Render HTMX partials.

### 5.2 Uvicorn

Use Uvicorn as the local ASGI server.

Recommended version policy:

```text
uvicorn[standard]>=0.49,<0.50
```

Default local address:

```text
http://localhost:8000
```

Recommended development command:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Recommended production-like local command:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Do not expose the local app on `0.0.0.0` by default.

### 5.3 Pydantic

Use Pydantic v2 for request, metadata, scene, prompt, and generation schemas.

Recommended version policy:

```text
pydantic>=2,<3
pydantic-settings>=2,<3
```

Use strict models for:

- `ProjectMetadata`
- `StoryMetadata`
- `CharacterMetadata`
- `SceneList`
- `Scene`
- `PromptList`
- `Prompt`
- `GenerationSettings`
- `Manifest`
- Error responses

### 5.4 File Upload Support

Required packages:

```text
python-multipart>=0.0.20,<1
```

FastAPI needs this for multipart file uploads.

### 5.5 File IO

Recommended packages:

```text
aiofiles>=24,<25
orjson>=3,<4
```

Use:

- `pathlib` for paths.
- Atomic write strategy for JSON files.
- Project-relative paths in metadata where possible.

---

## 6. Frontend Stack

### 6.1 Rendering Approach

Use server-rendered HTML with Jinja2.

Recommended version policy:

```text
Jinja2>=3.1.6,<3.2
```

UI pages and partials should be rendered by FastAPI routes.

### 6.2 HTMX

Use HTMX for interactive local UI behavior.

Recommended version:

```text
htmx.org 2.0.10
```

Use a local vendored file instead of relying on CDN at runtime.

Recommended path:

```text
app/static/vendor/htmx/htmx.min.js
```

Reason:

- Local-first app should work without internet after setup.
- Avoids CDN availability issues.
- Keeps the app simple without npm.

### 6.3 CSS

Use plain CSS for Phase 1.

Recommended path:

```text
app/static/css/app.css
```

Do not add Tailwind, Vite, npm, React, Next.js, or frontend bundlers unless explicitly approved later.

### 6.4 UI Pattern

Use a simple step-based workflow:

```text
Home
Create Project
Upload Story
Upload Characters
Scene Review
Prompt Review / Generation Settings
Generation Progress
Output Review
```

HTMX should be used for:

- Upload status partials.
- Validation result partials.
- Scene card edit/save interactions.
- Generation progress polling.
- Retry failed scene actions.

---

## 7. OpenAI Stack

### 7.1 Python SDK

Use the official OpenAI Python SDK.

Recommended version policy:

```text
openai>=2.41,<3
```

### 7.2 Model Identifier

The product decision name was:

```text
gpt 5.4 mini
```

Use this API model identifier in implementation:

```text
gpt-5.4-mini
```

Recommended environment variable:

```env
OPENAI_SCENE_MODEL=gpt-5.4-mini
OPENAI_PROMPT_MODEL=gpt-5.4-mini
```

Both scene splitting and prompt generation may use the same model in Phase 1.

### 7.3 API Key

Use environment variable:

```env
OPENAI_API_KEY=...
```

Do not store the API key inside project metadata, logs, prompts, or generated manifests.

### 7.4 JSON Output

The OpenAI client code must request JSON output for scene splitting and prompt generation.

Implementation rule:

- Use the current OpenAI SDK-supported JSON response mode or structured output mechanism.
- Validate all GPT output with Pydantic before saving it as trusted metadata.
- Treat GPT responses as untrusted until schema validation passes.

### 7.5 OpenAI Usage Boundaries

OpenAI is used for:

- Story understanding.
- Character candidate extraction.
- Scene splitting.
- Scene summarization.
- Prompt generation.
- Prompt enrichment.

OpenAI is not used for:

- Cloud image generation.
- Video generation.
- Remote rendering.
- Account system.

---

## 8. Local Image Generation Stack

## 8.1 Core AI Packages

Recommended base package policy:

```text
torch==2.7.*
torchvision==compatible-with-installed-torch
torchaudio==compatible-with-installed-torch
diffusers>=0.38,<0.39
transformers>=5.10,<6
accelerate>=1.13,<2
safetensors>=0.5,<1
huggingface-hub>=0.33,<1
Pillow>=11,<12
numpy>=2,<3
```

Important rule:

Install PyTorch using the official PyTorch selector command for Windows, Python, pip, and the chosen CUDA runtime. Do not install arbitrary `torch` wheels from random sources.

### 8.2 Recommended PyTorch Install Paths

For NVIDIA GPU machines, use the official PyTorch CUDA wheel matching the selected CUDA runtime.

Example pattern:

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

If CUDA 12.8 causes local compatibility issues, use the official PyTorch selector to choose a currently supported CUDA option such as CUDA 12.6.

CPU fallback install pattern:

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

The installer/startup script should detect whether CUDA is available with:

```python
import torch
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
```

### 8.3 Diffusers Role

Diffusers owns:

- Loading SDXL pipeline.
- Loading SD 1.5 fallback pipeline.
- Running image generation.
- Applying memory optimizations.
- Integrating IP-Adapter or IP-Adapter-FaceID when supported.

### 8.4 Main Model Direction

Primary model family:

```text
SDXL
```

The exact default SDXL checkpoint is still a product/quality decision and should be finalized in `docs/09-generation-pipeline.md`.

Tech stack default placeholder:

```env
IMAGE_MODEL_ID=stabilityai/stable-diffusion-xl-base-1.0
```

This is a conservative baseline model identifier, not the final anime-tuned model choice.

### 8.5 Anime-Tuned Model Policy

Phase 1 may later choose an anime-tuned SDXL model, but the implementation must not hardcode an unreviewed model as the only path.

Model ID must be configurable:

```env
IMAGE_MODEL_ID=...
LOW_VRAM_IMAGE_MODEL_ID=...
```

Recommended config behavior:

- Use `IMAGE_MODEL_ID` for SDXL path.
- Use `LOW_VRAM_IMAGE_MODEL_ID` for SD 1.5 fallback path.
- Store selected model IDs in `metadata/generation_settings.json`.
- Store actual model ID used per output in `outputs/manifest.json`.

---

## 9. Character Consistency Stack

### 9.1 Selected Method

Use this selected Phase 1 character consistency direction:

```text
IP-Adapter-FaceID
```

All future technical docs that mention character consistency must use this approach unless the product decision changes.

### 9.2 Required Runtime Components

IP-Adapter-FaceID may require:

```text
IP-Adapter-FaceID weights
InsightFace
ONNX Runtime / ONNX Runtime GPU
OpenCV
```

Recommended package policy:

```text
insightface>=0.7,<1
onnxruntime-gpu>=1.26,<2    # GPU path
onnxruntime>=1.26,<2        # CPU fallback for face analysis only
opencv-python-headless>=4.10,<5
```

Important:

- Do not install both `onnxruntime` and `onnxruntime-gpu` blindly in the same environment unless tested.
- Prefer one configured provider path per environment.
- Windows installation for InsightFace/ONNX Runtime can be fragile, so this must be tested early in the generation pipeline spike.

### 9.3 Character Consistency Dependency Mode

The app should support these runtime modes:

| Mode | Use Case | Behavior |
|---|---|---|
| `faceid_enabled` | GPU has enough VRAM and dependencies work | Use IP-Adapter-FaceID. |
| `faceid_disabled_low_vram` | 4GB VRAM or unsafe config | Disable IP-Adapter-FaceID and use prompt-based hints. |
| `faceid_unavailable` | Missing dependencies | Show warning and use accepted fallback if allowed. |
| `prompt_only` | Fallback mode | Character name + outfit + reference-derived metadata only. |

### 9.4 4GB VRAM Rule

The Phase 1 minimum hardware target is:

```text
4GB VRAM
```

But this does **not** mean SDXL + IP-Adapter-FaceID is guaranteed to run on 4GB VRAM.

Required behavior on 4GB VRAM:

1. Treat as low-VRAM mode.
2. Disable IP-Adapter-FaceID by default.
3. Prefer SD 1.5 fallback or lower-resolution preset.
4. Use prompt-based character hints.
5. Show plain-language warning in UI.
6. Allow advanced override only if implemented intentionally.

### 9.5 Prompt-Based Character Fallback

When IP-Adapter-FaceID is disabled, prompts must still include:

- Character name.
- Same outfit reminder.
- Same visual identity reminder.
- Any reliable user-provided or story-derived non-invented character notes.

Do not pretend the app extracted detailed visual traits from an image unless a separate image-captioning step is implemented.

---

## 10. Hardware Detection Stack

### 10.1 Required Detection

GPU detection should be included in Phase 1 because the app needs low-VRAM fallback behavior.

Use PyTorch for first-pass detection:

```python
import torch

def detect_generation_device():
    if torch.cuda.is_available():
        index = 0
        props = torch.cuda.get_device_properties(index)
        total_vram_gb = props.total_memory / (1024 ** 3)
        return {
            "device": "cuda",
            "name": props.name,
            "vram_gb": round(total_vram_gb, 2),
        }
    return {
        "device": "cpu",
        "name": "CPU",
        "vram_gb": 0,
    }
```

### 10.2 Hardware Profiles

Recommended internal hardware profiles:

| Profile | Detection | Default behavior |
|---|---|---|
| `cpu_only` | No CUDA GPU | Allow CPU fallback with warning. |
| `low_vram_4gb` | CUDA GPU <= 4GB VRAM | SD 1.5 or Low VRAM Preview; FaceID off. |
| `mid_vram_6_8gb` | 6–8GB VRAM | SDXL may work with optimizations; FaceID cautious. |
| `high_vram_12gb_plus` | 12GB+ VRAM | SDXL + FaceID likely safer. |

### 10.3 Detection Output File

Recommended metadata path:

```text
metadata/generation_settings.json
```

Example:

```json
{
  "hardware": {
    "device": "cuda",
    "gpu_name": "NVIDIA GeForce RTX 3050 Laptop GPU",
    "vram_gb": 4.0,
    "hardware_profile": "low_vram_4gb"
  },
  "character_consistency": {
    "method": "ip_adapter_faceid",
    "enabled": false,
    "disabled_reason": "low_vram_default"
  }
}
```

---

## 11. Image Generation Presets

### 11.1 Output Presets

The app must provide presets instead of one hardcoded resolution.

| Preset ID | Name | Width | Height | Aspect Ratio | Notes |
|---|---|---:|---:|---|---|
| `youtube_standard` | YouTube Standard | 1280 | 720 | 16:9 | Default. |
| `youtube_high` | YouTube High | 1920 | 1080 | 16:9 | Higher VRAM. |
| `low_vram_preview` | Low VRAM Preview | 960 | 540 | 16:9 | Recommended for 4GB VRAM. |
| `low_vram_tiny` | Low VRAM Tiny | 768 | 432 | 16:9 | Optional emergency fallback. |
| `square_preview` | Square Preview | 1024 | 1024 | 1:1 | Optional. |
| `vertical_short` | Vertical Short | 1080 | 1920 | 9:16 | Optional. |

### 11.2 Default Preset

Default:

```text
YouTube Standard — 1280x720, 16:9
```

### 11.3 Low-VRAM Override

If hardware profile is `low_vram_4gb`, the app should recommend:

```text
Low VRAM Preview — 960x540
```

It may still allow YouTube Standard if the selected fallback pipeline can handle it, but the UI should warn the user.

---

## 12. Local Storage Stack

### 12.1 Storage Decision

Use local folder + JSON files for Phase 1.

Do not introduce a database unless explicitly approved later.

### 12.2 Folder Structure

Use this shared structure:

```text
projects/
  {project_id}/
    input/
      story.md
      characters/
        Akira.png
        Hana.png
    metadata/
      project.json
      story.json
      characters.json
      scenes.json
      prompts.json
      generation_settings.json
      character_cache/
    outputs/
      images/
        001_scene.png
        002_scene.png
      manifest.json
    logs/
      app.log
      generation.log
```

### 12.3 JSON File Handling

Rules:

- Write JSON with UTF-8 encoding.
- Use atomic writes: write temp file, then rename.
- Use stable schema versions in each JSON file.
- Use project-relative paths inside metadata where possible.
- Never store API keys in project files.
- Never silently delete stale outputs.

### 12.4 Database Decision

SQLite is not required for Phase 1 MVP.

If project history later becomes complex, SQLite can be considered in a future document, but the current implementation should remain JSON-first.

---

## 13. Logging Stack

### 13.1 Package

Use Python standard `logging`.

Optional formatting package:

```text
rich>=13,<14
```

Only add `rich` if it improves developer logs without complicating the app.

### 13.2 Log Files

Global app log:

```text
logs/app.log
```

Project logs:

```text
projects/{project_id}/logs/app.log
projects/{project_id}/logs/generation.log
```

### 13.3 Logging Rules

Log:

- Project creation.
- Upload validation result.
- Scene splitting request metadata.
- OpenAI model used.
- Token usage if returned by SDK.
- GPT validation failures.
- Prompt generation status.
- Image generation start/end per scene.
- Model ID used.
- Hardware profile.
- FaceID enabled/disabled state.
- Per-scene generation errors.

Do not log:

- OpenAI API key.
- Full raw story content repeatedly.
- Sensitive absolute local paths unless debug mode is enabled.
- Large image blobs.

---

## 14. Configuration Stack

### 14.1 Environment File

Use `.env` for local developer/user configuration.

Recommended package:

```text
python-dotenv>=1,<2
```

### 14.2 Required Environment Variables

```env
OPENAI_API_KEY=
OPENAI_SCENE_MODEL=gpt-5.4-mini
OPENAI_PROMPT_MODEL=gpt-5.4-mini
PROJECTS_ROOT=./projects
APP_HOST=127.0.0.1
APP_PORT=8000
```

### 14.3 Optional Environment Variables

```env
IMAGE_MODEL_ID=stabilityai/stable-diffusion-xl-base-1.0
LOW_VRAM_IMAGE_MODEL_ID=stable-diffusion-v1-5/stable-diffusion-v1-5
DEFAULT_OUTPUT_PRESET=youtube_standard
ENABLE_IP_ADAPTER_FACEID=auto
FORCE_LOW_VRAM_MODE=false
LOG_LEVEL=INFO
```

### 14.4 Config Precedence

Recommended precedence:

```text
Environment variables
→ .env
→ project generation_settings.json
→ app defaults
```

Secrets must only come from environment variables or `.env`, never from project metadata.

---

## 15. Dependency Files

### 15.1 Recommended Files

```text
requirements/base.txt
requirements/ai-cu128.txt
requirements/ai-cpu.txt
requirements/dev.txt
```

### 15.2 `requirements/base.txt`

Recommended content:

```text
fastapi>=0.136,<0.137
uvicorn[standard]>=0.49,<0.50
Jinja2>=3.1.6,<3.2
python-multipart>=0.0.20,<1
pydantic>=2,<3
pydantic-settings>=2,<3
python-dotenv>=1,<2
aiofiles>=24,<25
orjson>=3,<4
Pillow>=11,<12
nh3>=0.2,<1
markdown-it-py>=3,<4
openai>=2.41,<3
```

### 15.3 `requirements/ai-cu128.txt`

Do not put the PyTorch CUDA wheel here unless the installer command uses the official PyTorch index.

Recommended content after PyTorch installation:

```text
diffusers>=0.38,<0.39
transformers>=5.10,<6
accelerate>=1.13,<2
safetensors>=0.5,<1
huggingface-hub>=0.33,<1
numpy>=2,<3
opencv-python-headless>=4.10,<5
insightface>=0.7,<1
onnxruntime-gpu>=1.26,<2
```

### 15.4 `requirements/ai-cpu.txt`

```text
diffusers>=0.38,<0.39
transformers>=5.10,<6
accelerate>=1.13,<2
safetensors>=0.5,<1
huggingface-hub>=0.33,<1
numpy>=2,<3
opencv-python-headless>=4.10,<5
insightface>=0.7,<1
onnxruntime>=1.26,<2
```

### 15.5 `requirements/dev.txt`

```text
pytest>=8,<9
pytest-asyncio>=1,<2
httpx>=0.28,<1
ruff>=0.11,<1
mypy>=1.15,<2
types-Pillow
```

---

## 16. Windows Setup Scripts

### 16.1 MVP Script List

Recommended scripts:

```text
scripts/
  setup_windows_gpu.bat
  setup_windows_cpu.bat
  run_windows.bat
  check_gpu.py
```

### 16.2 `setup_windows_gpu.bat` Responsibilities

1. Check Python version.
2. Create `.venv`.
3. Activate `.venv`.
4. Upgrade `pip`.
5. Install base requirements.
6. Install PyTorch CUDA wheel using official PyTorch index.
7. Install AI requirements.
8. Run `check_gpu.py`.
9. Print clear success/failure message.

### 16.3 `setup_windows_cpu.bat` Responsibilities

1. Check Python version.
2. Create `.venv`.
3. Activate `.venv`.
4. Upgrade `pip`.
5. Install base requirements.
6. Install CPU PyTorch wheel.
7. Install CPU AI requirements.
8. Print warning that CPU generation is slow.

### 16.4 `run_windows.bat` Responsibilities

1. Activate `.venv`.
2. Start FastAPI on `127.0.0.1:8000`.
3. Open browser to `http://localhost:8000`.

---

## 17. Recommended Repository Structure

```text
local-ai-anime-storyboard-generator/
  app/
    main.py
    core/
      config.py
      logging.py
      paths.py
      errors.py
    web/
      routes_home.py
      routes_projects.py
      routes_story.py
      routes_characters.py
      routes_scenes.py
      routes_generation.py
      routes_prompts.py
      routes_outputs.py
    services/
      project_service.py
      story_service.py
      character_service.py
      openai_scene_service.py
      openai_prompt_service.py
      generation_service.py
      hardware_service.py
      manifest_service.py
    schemas/
      project.py
      story.py
      character.py
      scene.py
      prompt.py
      generation.py
      manifest.py
      errors.py
    templates/
      base.html
      home.html
      project_dashboard.html
      story_upload.html
      character_upload.html
      scene_review.html
      prompt_review.html
      generation_progress.html
      output_review.html
      partials/
    static/
      css/
        app.css
      vendor/
        htmx/
          htmx.min.js
  projects/
    .gitkeep
  logs/
    .gitkeep
  requirements/
    base.txt
    ai-cu128.txt
    ai-cpu.txt
    dev.txt
  scripts/
    setup_windows_gpu.bat
    setup_windows_cpu.bat
    run_windows.bat
    check_gpu.py
  tests/
    unit/
    integration/
  .env.example
  README.md
```

---

## 18. Security and Privacy Stack

### 18.1 Localhost Binding

Default bind address:

```text
127.0.0.1
```

Do not bind to public network interfaces by default.

### 18.2 File Upload Security

Use safe path handling:

- Never trust uploaded filenames as paths.
- Strip directory components.
- Reject path traversal like `../file.md`.
- Store files only under the project folder.
- Validate extension and actual decodability.

### 18.3 Markdown Safety

If rendering story preview as HTML, sanitize it.

Recommended packages:

```text
markdown-it-py>=3,<4
nh3>=0.2,<1
```

Raw story HTML must not execute scripts in the local UI.

### 18.4 OpenAI Privacy Notice

The UI must clearly tell users:

```text
Scene splitting and prompt generation use the OpenAI API. Your story text may be sent for analysis when you run these steps.
```

Generated images and character reference files should not be uploaded to a cloud renderer in Phase 1.

---

## 19. Testing Stack

### 19.1 Test Framework

Use:

```text
pytest>=8,<9
pytest-asyncio>=1,<2
httpx>=0.28,<1
```

### 19.2 Linting and Formatting

Use:

```text
ruff>=0.11,<1
```

Ruff should handle:

- Formatting.
- Import sorting.
- Basic lint rules.

### 19.3 Type Checking

Use:

```text
mypy>=1.15,<2
```

Type checking should be strict for:

- Pydantic schemas.
- Services.
- Project file handling.
- OpenAI response parsing.
- Generation config models.

### 19.4 Test Categories

Required test categories:

- Story upload validation.
- Character image validation.
- Filename-to-character mapping.
- Scene JSON validation.
- Prompt JSON validation.
- Project folder creation.
- Atomic metadata writing.
- Output filename ordering.
- Low-VRAM hardware profile logic.
- Generation readiness checks.

Do not require real OpenAI or real GPU calls in unit tests.

---

## 20. Technologies Explicitly Out of Scope

Do not add these in Phase 1:

```text
React
Next.js
Vue
Svelte
Tailwind build pipeline
Vite
Webpack
Node-required frontend build
PostgreSQL
MySQL
MongoDB
Redis
Kafka
RabbitMQ
Celery
Cloud rendering
Hosted auth
Keycloak
Docker-only setup
Kubernetes
ComfyUI graph editor
LoRA training workflow
DreamBooth training workflow
Video generation
Voice generation
Lip-sync
Subtitle generation
Timeline export
```

Notes:

- Docker may be added later as an optional developer convenience, but it must not be the only supported workflow.
- SQLite may be considered later for project history, but Phase 1 metadata is JSON-first.
- LoRA weights used internally by an adapter model are not the same as implementing user-facing LoRA training. Do not add character LoRA training.

---

## 21. Known Technical Risks

### 21.1 Risk: SDXL Is Too Heavy for 4GB VRAM

Mitigation:

- Treat 4GB as low-VRAM mode.
- Provide SD 1.5 fallback.
- Provide Low VRAM Preview preset.
- Disable IP-Adapter-FaceID by default on 4GB VRAM.
- Log the selected hardware profile.

### 21.2 Risk: IP-Adapter-FaceID Dependencies Are Fragile on Windows

Mitigation:

- Isolate FaceID setup in the generation pipeline.
- Add a startup/runtime health check.
- Provide prompt-only fallback.
- Keep FaceID off by default on low-VRAM machines.
- Test InsightFace + ONNX Runtime early.

### 21.3 Risk: OpenAI Model Identifier Changes

Mitigation:

- Store model ID in environment variables.
- Log model ID used.
- Keep default as `gpt-5.4-mini` until changed in docs and code together.

### 21.4 Risk: GPT Returns Invalid JSON

Mitigation:

- Use JSON response mode or structured output.
- Validate with Pydantic.
- Save raw failed response only in debug/error logs.
- Show retry UI.

### 21.5 Risk: Non-Technical Users Get Overwhelmed

Mitigation:

- Hide advanced model settings.
- Use presets.
- Use plain-language warnings.
- Do not expose adapter internals in the default UI.

---

## 22. Implementation Readiness Checklist

Before coding begins, confirm:

- [ ] Python 3.12.x is installed on the Windows target machine.
- [ ] `OPENAI_API_KEY` is configured.
- [ ] `gpt-5.4-mini` works with the selected OpenAI SDK call style.
- [ ] FastAPI app starts at `http://localhost:8000`.
- [ ] HTMX is vendored locally.
- [ ] PyTorch GPU install works on the target NVIDIA machine.
- [ ] `torch.cuda.is_available()` returns expected result.
- [ ] Diffusers can load the chosen SDXL model.
- [ ] SD 1.5 fallback model is configured.
- [ ] IP-Adapter-FaceID dependency spike is completed.
- [ ] Low-VRAM mode disables FaceID by default.
- [ ] Project folder JSON writes are atomic.
- [ ] Output filenames use numeric prefixes.

---

## 23. Final Phase 1 Tech Stack Definition

Phase 1 should be implemented as a single local Python application:

```text
Python 3.12
FastAPI
Jinja2
HTMX
Pydantic v2
OpenAI Python SDK with gpt-5.4-mini
PyTorch
Diffusers
SDXL primary generation path
SD 1.5 low-VRAM fallback
IP-Adapter-FaceID hardware-conditional character consistency
Local JSON metadata
Local project folders
Windows-first .bat setup and run scripts
```

This stack intentionally avoids unnecessary infrastructure so the MVP stays buildable, local-first, and friendly for non-technical creators.
