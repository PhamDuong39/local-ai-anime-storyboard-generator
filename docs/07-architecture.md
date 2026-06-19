# Local AI Anime Storyboard Generator — Simple Architecture

**Document:** `docs/07-architecture.md`  
**Product name:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Status:** Draft based on confirmed docs `00`–`06`  
**Primary user:** Non-technical anime/story creator  

---

## 1. Purpose

This document defines the Phase 1 architecture for the Local AI Anime Storyboard Generator.

The goal is to make the architecture simple enough for Codex Agent to implement without guessing, while still keeping the system clean, testable, and safe for local AI generation.

This is **not** an enterprise architecture document. Do not add advanced patterns unless they directly help the MVP.

Phase 1 must stay:

- Local-first.
- Windows-first.
- Image-only.
- Single-user.
- Simple FastAPI app.
- JSON-file based.
- Easy for a coding agent to implement task by task.

---

## 2. Architecture Summary

Phase 1 is a single local Python web application.

```text
Browser on user's machine
  ↓
FastAPI local server at 127.0.0.1:8000
  ↓
Server-rendered Jinja2 pages + HTMX partial updates
  ↓
Application services
  ↓
Local JSON metadata + local files + local Diffusers generation
  ↓
Structured project output folder
```

The app uses OpenAI API only for:

- Story understanding.
- Scene splitting.
- Prompt generation.

The app uses local machine resources for:

- Character image validation.
- Hardware detection.
- Diffusers image generation.
- IP-Adapter-FaceID when hardware supports it.
- Output image storage.

There is no cloud renderer, no hosted backend, no account system, no queue broker, and no microservice split in Phase 1.

---

## 3. Non-Goals

Do not implement these in the Phase 1 architecture:

- Microservices.
- Kafka, RabbitMQ, Redis, Celery, or external queue systems.
- React, Next.js, Vue, Svelte, Vite, or npm-required frontend build.
- PostgreSQL, MySQL, MongoDB, or required SQLite database.
- Docker-only workflow.
- Hosted authentication.
- Multi-user cloud server.
- Cloud rendering.
- Video generation.
- Voice generation.
- Lip-sync.
- Subtitle generation.
- Timeline export.
- User-facing LoRA training.
- ComfyUI graph editor.

SQLite may be considered later, but Phase 1 architecture uses local folders and JSON files.

---

## 4. Core Architectural Rules

### 4.1 Single Local App

The whole MVP runs as one local FastAPI process.

```text
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The app must bind to:

```text
127.0.0.1
```

Do not bind to `0.0.0.0` by default.

### 4.2 Server-Rendered UI

The UI is built with:

```text
Jinja2 + HTMX + plain CSS
```

The backend renders full pages and HTMX partials.

No frontend build pipeline is required.

### 4.3 Local JSON Storage

Project state is stored in local JSON files under:

```text
projects/{project_id}/metadata/
```

Do not introduce a database for Phase 1 unless explicitly approved later.

### 4.4 Mandatory Scene Approval

Image generation must never start unless:

1. Story is uploaded and valid.
2. Character references are uploaded and validated.
3. Scene splitting has completed.
4. User has reviewed scenes.
5. User has explicitly approved the scene list.
6. Prompts have been generated and validated.

### 4.5 Ordered Output

Every generated image must preserve story order by filename prefix.

Example:

```text
001_akira_enters_school.png
002_hana_warning.png
003_dark_hallway.png
```

### 4.6 Low-VRAM Safety

4GB VRAM is treated as low-VRAM mode.

On 4GB VRAM machines:

- Prefer SD 1.5 fallback or low-resolution preset.
- Disable IP-Adapter-FaceID by default.
- Use prompt-based character hints.
- Show plain-language warning.

### 4.7 Canonical Character Consistency Value

Human-readable method name:

```text
IP-Adapter-FaceID
```

Persisted JSON/config/manifest value:

```text
ip-adapter-faceid
```

Do not use underscore-based variants for this persisted value.

---

## 5. High-Level Component Diagram

```text
┌────────────────────────────────────────────────────────────┐
│ Browser                                                     │
│ - HTML pages                                                │
│ - HTMX interactions                                         │
│ - Upload forms                                              │
│ - Scene review UI                                           │
│ - Generation progress polling                               │
└───────────────────────────┬────────────────────────────────┘
                            │ HTTP localhost
                            ↓
┌────────────────────────────────────────────────────────────┐
│ FastAPI App                                                 │
│ - Web routes                                                │
│ - HTMX partial routes                                       │
│ - Request validation                                        │
│ - Error rendering                                           │
└───────────────────────────┬────────────────────────────────┘
                            │ calls services
                            ↓
┌────────────────────────────────────────────────────────────┐
│ Application Services                                        │
│ - ProjectService                                            │
│ - StoryService                                              │
│ - CharacterService                                          │
│ - OpenAISceneService                                        │
│ - OpenAIPromptService                                       │
│ - HardwareService                                           │
│ - GenerationService                                         │
│ - ManifestService                                           │
│ - JobService                                                │
└───────────────┬───────────────────────┬────────────────────┘
                │                       │
                ↓                       ↓
┌────────────────────────────┐  ┌────────────────────────────┐
│ Local Project Files         │  │ External / Local AI         │
│ - story.md                  │  │ - OpenAI API                │
│ - character images          │  │ - PyTorch                   │
│ - metadata JSON             │  │ - Diffusers                 │
│ - output images             │  │ - SDXL / SD 1.5             │
│ - logs                      │  │ - IP-Adapter-FaceID         │
└────────────────────────────┘  └────────────────────────────┘
```

---

## 6. Runtime Architecture

### 6.1 Process Model

Use one Python process for Phase 1:

```text
FastAPI app process
  ├── serves UI routes
  ├── reads/writes local files
  ├── calls OpenAI API
  ├── runs local generation jobs
  └── writes progress state
```

Do not split generation into a separate service for Phase 1.

### 6.2 Long-Running Generation

Image generation can take a long time. The UI must not freeze.

Use a simple in-process job runner.

Recommended MVP approach:

```text
User clicks Generate Images
  ↓
FastAPI creates a generation job record in metadata
  ↓
FastAPI starts an in-process background task/thread
  ↓
GenerationService processes scenes one by one
  ↓
Job status is written to generation_status.json
  ↓
HTMX polls progress endpoint
  ↓
UI updates progress
```

Allowed implementation options:

- FastAPI `BackgroundTasks` for very simple runs.
- A small internal `ThreadPoolExecutor(max_workers=1)` for better job tracking.

Recommended for Phase 1:

```text
ThreadPoolExecutor(max_workers=1)
```

Reason:

- Avoids adding Celery or queues.
- Prevents multiple heavy GPU jobs from running at once.
- Keeps implementation clear for Codex.

### 6.3 Job Concurrency Rule

Only one generation job should run at a time per local app process.

If a job is already running, the UI should show:

```text
Generation is already running. Please wait or cancel the current job first.
```

Phase 1 does not need complex multi-project parallel generation.

---

## 7. Recommended Repository Architecture

```text
local-ai-anime-storyboard-generator/
  app/
    main.py
    core/
      config.py
      logging.py
      paths.py
      errors.py
      file_io.py
    web/
      routes_home.py
      routes_projects.py
      routes_story.py
      routes_characters.py
      routes_scenes.py
      routes_prompts.py
      routes_generation.py
      routes_outputs.py
    services/
      project_service.py
      story_service.py
      character_service.py
      openai_scene_service.py
      openai_prompt_service.py
      hardware_service.py
      generation_service.py
      generation_job_service.py
      manifest_service.py
    schemas/
      project.py
      story.py
      character.py
      scene.py
      prompt.py
      generation.py
      manifest.py
      jobs.py
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
        _flash.html
        _story_validation.html
        _character_validation.html
        _scene_card.html
        _generation_status.html
        _output_grid.html
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

## 8. Layer Responsibilities

## 8.1 `app/main.py`

Responsibilities:

- Create FastAPI app.
- Register routers.
- Mount static files.
- Configure template directory.
- Configure exception handlers.
- Run startup checks that are safe and fast.

Do not put business logic in `main.py`.

---

## 8.2 `app/core/`

### `config.py`

Responsibilities:

- Load environment variables.
- Define app settings with Pydantic Settings.
- Provide defaults for model IDs and local paths.
- Never log secrets.

Key settings:

```text
OPENAI_API_KEY
OPENAI_SCENE_MODEL
OPENAI_PROMPT_MODEL
PROJECTS_ROOT
APP_HOST
APP_PORT
IMAGE_MODEL_ID
LOW_VRAM_IMAGE_MODEL_ID
ENABLE_IP_ADAPTER_FACEID
FORCE_LOW_VRAM_MODE
LOG_LEVEL
```

### `paths.py`

Responsibilities:

- Build safe project paths.
- Prevent path traversal.
- Normalize Windows-safe paths.
- Return project-relative paths for metadata.

### `file_io.py`

Responsibilities:

- Read JSON.
- Write JSON atomically.
- Create folders.
- Compute file hashes.
- Avoid partial metadata writes.

Atomic write rule:

```text
write to file.tmp
flush/close
replace original with tmp using atomic rename
```

### `errors.py`

Responsibilities:

- Define app error classes.
- Define error codes.
- Map errors to user-facing messages.
- Support both JSON-style and HTML partial error rendering.

---

## 8.3 `app/web/`

Web route modules own HTTP and UI concerns only.

They should:

- Read form data.
- Validate request-level inputs.
- Call services.
- Render templates or partials.
- Redirect to the next workflow step.

They should not:

- Directly call OpenAI.
- Directly run Diffusers.
- Directly manipulate complex metadata.
- Implement business rules inline.

Example route ownership:

| Route module | Responsibility |
|---|---|
| `routes_home.py` | Home page, open existing project entry. |
| `routes_projects.py` | Create project, project dashboard. |
| `routes_story.py` | Upload story, preview story, validate story. |
| `routes_characters.py` | Upload/delete character refs, validation result. |
| `routes_scenes.py` | Split scenes, review scenes, edit/reorder/approve scenes. |
| `routes_prompts.py` | Generate prompts, review/edit prompts. |
| `routes_generation.py` | Start generation, poll status, retry failed scenes, cancel if supported. |
| `routes_outputs.py` | Output review, open folder helper if implemented. |

---

## 8.4 `app/services/`

Services own application behavior.

### `ProjectService`

Responsibilities:

- Create project folder.
- Create initial metadata files.
- Load project metadata.
- Update project status.
- List existing projects if implemented.

### `StoryService`

Responsibilities:

- Validate `.md` upload.
- Decode UTF-8.
- Normalize text.
- Save `input/story.md`.
- Save `metadata/story.json`.
- Mark scene/prompt/output data as stale when story changes.

### `CharacterService`

Responsibilities:

- Validate character image extension.
- Decode image with Pillow.
- Extract dimensions and file size.
- Derive character name from filename stem.
- Reject duplicate character names.
- Save image under `input/characters/`.
- Save `metadata/characters.json`.
- Validate detected scene characters against uploaded references.

### `OpenAISceneService`

Responsibilities:

- Build scene splitting request.
- Call OpenAI API.
- Request JSON/structured output.
- Validate response using Pydantic.
- Save draft `metadata/scenes.json`.

### `OpenAIPromptService`

Responsibilities:

- Load approved scenes.
- Load character metadata.
- Build prompt generation request.
- Call OpenAI API.
- Validate prompt JSON.
- Save `metadata/prompts.json`.

### `HardwareService`

Responsibilities:

- Detect CPU/GPU.
- Detect CUDA availability.
- Detect VRAM.
- Produce hardware profile.
- Decide default generation mode.
- Save hardware snapshot in `generation_settings.json`.

### `GenerationService`

Responsibilities:

- Load prompts.
- Load generation settings.
- Select SDXL or SD 1.5 path.
- Decide whether IP-Adapter-FaceID is enabled.
- Generate images scene by scene.
- Save output image files.
- Update manifest.
- Update job progress.
- Log per-scene errors.

### `GenerationJobService`

Responsibilities:

- Create generation job records.
- Start one in-process job at a time.
- Store job state.
- Support progress polling.
- Support retry failed scene jobs if implemented.
- Support cancellation if implemented.

### `ManifestService`

Responsibilities:

- Create/update `outputs/manifest.json`.
- Map scene IDs to output filenames.
- Store model ID used.
- Store generation settings snapshot.
- Store character references used.
- Store success/failure state.

---

## 9. Schema Layer

All persistent JSON files must have Pydantic schemas.

Recommended schema modules:

| Module | Main models |
|---|---|
| `project.py` | `ProjectMetadata`, `ProjectStatus`, `OutputPreset` |
| `story.py` | `StoryMetadata`, `StoryStatus` |
| `character.py` | `CharacterMetadata`, `CharacterReference`, `CharacterStatus` |
| `scene.py` | `SceneList`, `Scene`, `SceneStatus` |
| `prompt.py` | `PromptList`, `Prompt`, `PromptStatus` |
| `generation.py` | `GenerationSettings`, `HardwareProfile`, `GenerationMode` |
| `manifest.py` | `OutputManifest`, `OutputAsset` |
| `jobs.py` | `GenerationJob`, `GenerationJobStatus` |
| `errors.py` | `AppErrorResponse` |

Rules:

- Treat file contents and GPT responses as untrusted until schema validation passes.
- Include `version` fields in persisted metadata files.
- Store project-relative paths where possible.
- Keep enums stable and lowercase.
- Avoid nullable fields unless the field is truly optional.

---

## 10. Project Folder Architecture

Use this structure for every project:

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
      generation_status.json
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

### 10.1 Required Files by Workflow Step

| Step | Required files created/updated |
|---|---|
| Create project | `metadata/project.json`, folders |
| Upload story | `input/story.md`, `metadata/story.json` |
| Upload characters | `input/characters/*`, `metadata/characters.json` |
| Split scenes | `metadata/scenes.json` |
| Approve scenes | `metadata/scenes.json` |
| Generate prompts | `metadata/prompts.json` |
| Detect hardware / configure generation | `metadata/generation_settings.json` |
| Run generation | `metadata/generation_status.json`, `outputs/images/*`, `outputs/manifest.json`, logs |

### 10.2 Path Storage Rule

Store project-relative paths in metadata.

Good:

```json
{
  "stored_path": "input/characters/Akira.png"
}
```

Avoid:

```json
{
  "stored_path": "C:\\Users\\User\\Desktop\\app\\projects\\abc\\input\\characters\\Akira.png"
}
```

Absolute paths may appear only in debug logs when needed.

---

## 11. Project State Machine

Use simple project statuses.

```text
CREATED
  ↓
STORY_UPLOADED
  ↓
CHARACTERS_UPLOADED
  ↓
SCENES_GENERATED
  ↓
SCENES_APPROVED
  ↓
PROMPTS_GENERATED
  ↓
GENERATION_RUNNING
  ↓
GENERATION_COMPLETED
```

Failure/partial states:

```text
STORY_UPLOAD_FAILED
CHARACTER_VALIDATION_FAILED
SCENE_SPLITTING_FAILED
PROMPT_GENERATION_FAILED
GENERATION_FAILED
GENERATION_PARTIAL
```

### 11.1 State Transition Rules

| From | To | Trigger |
|---|---|---|
| `CREATED` | `STORY_UPLOADED` | Valid story upload. |
| `STORY_UPLOADED` | `CHARACTERS_UPLOADED` | Valid character references saved. |
| `CHARACTERS_UPLOADED` | `SCENES_GENERATED` | GPT scene splitting succeeds. |
| `SCENES_GENERATED` | `SCENES_APPROVED` | User approves scene list. |
| `SCENES_APPROVED` | `PROMPTS_GENERATED` | Prompt generation succeeds. |
| `PROMPTS_GENERATED` | `GENERATION_RUNNING` | User starts generation. |
| `GENERATION_RUNNING` | `GENERATION_COMPLETED` | All scenes generated successfully. |
| `GENERATION_RUNNING` | `GENERATION_PARTIAL` | Some scenes fail. |
| Any recoverable step | Previous valid step | User replaces stale input or retries. |

Do not allow `GENERATION_RUNNING` unless scenes are approved and prompts are valid.

---

## 12. End-to-End Flow Architecture

## 12.1 Create Project Flow

```text
POST /projects
  ↓
routes_projects.py
  ↓
ProjectService.create_project()
  ↓
Create folders
  ↓
Write metadata/project.json
  ↓
Redirect to story upload page
```

## 12.2 Story Upload Flow

```text
POST /projects/{project_id}/story
  ↓
routes_story.py
  ↓
StoryService.validate_story_upload()
  ↓
StoryService.normalize_story_text()
  ↓
Save input/story.md
  ↓
Write metadata/story.json
  ↓
Render story validation partial or redirect
```

## 12.3 Character Upload Flow

```text
POST /projects/{project_id}/characters
  ↓
routes_characters.py
  ↓
CharacterService.validate_image()
  ↓
CharacterService.derive_character_name()
  ↓
Save input/characters/{name}.{ext}
  ↓
Write metadata/characters.json
  ↓
Render character validation partial
```

## 12.4 Scene Splitting Flow

```text
POST /projects/{project_id}/scenes/split
  ↓
routes_scenes.py
  ↓
OpenAISceneService.split_story_into_scenes()
  ↓
Load story + characters + output preset
  ↓
Call OpenAI JSON/structured output
  ↓
Validate SceneList with Pydantic
  ↓
Save metadata/scenes.json with draft scenes
  ↓
Render scene review page
```

## 12.5 Scene Review and Approval Flow

```text
User edits/reorders/deletes scene cards
  ↓
HTMX calls scene update/reorder routes
  ↓
Scene metadata is validated and saved
  ↓
User clicks Approve Scenes
  ↓
Scene statuses become approved
  ↓
Project status becomes SCENES_APPROVED
```

## 12.6 Prompt Generation Flow

```text
POST /projects/{project_id}/prompts/generate
  ↓
routes_prompts.py
  ↓
OpenAIPromptService.generate_prompts()
  ↓
Load approved scenes + characters + preset
  ↓
Call OpenAI JSON/structured output
  ↓
Validate PromptList with Pydantic
  ↓
Save metadata/prompts.json
  ↓
Render prompt review/settings page
```

## 12.7 Image Generation Flow

```text
POST /projects/{project_id}/generation/start
  ↓
routes_generation.py
  ↓
GenerationJobService.start_job()
  ↓
Validate generation readiness
  ↓
Create/update metadata/generation_status.json
  ↓
Run GenerationService in background thread
  ↓
For each scene:
      load prompt
      resolve character references
      select SDXL or SD 1.5 fallback
      enable FaceID only if safe
      generate image
      save output image
      update manifest
      update progress
  ↓
HTMX polls generation status
  ↓
UI shows progress and output review
```

---

## 13. Generation Architecture

### 13.1 Pipeline Selection

GenerationService chooses a pipeline based on hardware and settings.

```text
if cpu_only:
    use CPU fallback with warning
elif low_vram_4gb:
    use SD 1.5 fallback or low-resolution preset
    disable IP-Adapter-FaceID by default
elif mid_vram_6_8gb:
    use SDXL with memory optimizations if possible
    enable IP-Adapter-FaceID only if dependency check passes and config allows
elif high_vram_12gb_plus:
    use SDXL path
    enable IP-Adapter-FaceID if dependencies work
```

### 13.2 Character Consistency Decision

Inputs:

- Hardware profile.
- `ENABLE_IP_ADAPTER_FACEID` config.
- Character references present in scene.
- IP-Adapter-FaceID dependency health check.

Output example:

```json
{
  "method": "ip-adapter-faceid",
  "enabled": false,
  "disabled_reason": "low_vram_default"
}
```

If FaceID is disabled, prompts must still include character hints:

```text
Akira, same outfit and visual identity as uploaded reference image, anime style
```

### 13.3 Model Loading Rule

Model loading should be lazy.

Do not load SDXL at app startup.

Load generation models only when generation starts.

Reason:

- Faster app startup.
- Easier troubleshooting.
- Avoids GPU memory allocation before user needs it.

### 13.4 Scene-by-Scene Execution

Generate images one scene at a time.

Do not batch multiple scenes in Phase 1.

Reason:

- Lower VRAM pressure.
- Easier progress reporting.
- Easier retry for failed scenes.
- Simpler logs.

### 13.5 Per-Scene Failure Rule

If one scene fails:

- Mark that scene output as failed.
- Write error to `generation.log`.
- Update `generation_status.json`.
- Continue or stop based on simple config.

Recommended default:

```text
Continue generating remaining scenes when safe.
```

If the failure is global, such as model load failure or CUDA out-of-memory on first scene, stop the job and show a clear error.

---

## 14. Minimal Route Map

Exact API details belong in `docs/08-api-spec.md`, but the architecture expects these route groups.

### 14.1 Page Routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Home page. |
| `GET` | `/projects/new` | Create project form. |
| `POST` | `/projects` | Create project. |
| `GET` | `/projects/{project_id}` | Project dashboard. |
| `GET` | `/projects/{project_id}/story` | Story upload page. |
| `GET` | `/projects/{project_id}/characters` | Character upload page. |
| `GET` | `/projects/{project_id}/scenes` | Scene review page. |
| `GET` | `/projects/{project_id}/prompts` | Prompt review page. |
| `GET` | `/projects/{project_id}/generation` | Generation progress page. |
| `GET` | `/projects/{project_id}/outputs` | Output review page. |

### 14.2 Action / HTMX Routes

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/projects/{project_id}/story` | Upload story. |
| `POST` | `/projects/{project_id}/characters` | Upload character images. |
| `POST` | `/projects/{project_id}/scenes/split` | Run GPT scene splitting. |
| `POST` | `/projects/{project_id}/scenes/{scene_id}` | Update scene card. |
| `POST` | `/projects/{project_id}/scenes/reorder` | Reorder scenes. |
| `POST` | `/projects/{project_id}/scenes/approve` | Approve scene list. |
| `POST` | `/projects/{project_id}/prompts/generate` | Generate prompts. |
| `POST` | `/projects/{project_id}/prompts/{scene_id}` | Update prompt. |
| `POST` | `/projects/{project_id}/generation/start` | Start image generation. |
| `GET` | `/projects/{project_id}/generation/status` | Poll generation status partial. |
| `POST` | `/projects/{project_id}/generation/retry-failed` | Retry failed scenes if implemented. |

---

## 15. Error Handling Architecture

Use simple app exceptions and error codes.

```text
AppError
  ├── code
  ├── message
  ├── details
  └── http_status
```

Routes should catch known app errors and render friendly UI partials.

### 15.1 Error Categories

| Category | Example codes |
|---|---|
| Story | `STORY_FILE_REQUIRED`, `STORY_TOO_LARGE`, `STORY_INVALID_ENCODING` |
| Character | `UNSUPPORTED_CHARACTER_IMAGE_TYPE`, `DUPLICATE_CHARACTER_NAME`, `MISSING_CHARACTER_REFERENCE` |
| Scene | `SCENE_SPLIT_FAILED`, `SCENE_JSON_INVALID`, `SCENE_APPROVAL_REQUIRED` |
| Prompt | `PROMPT_GENERATION_FAILED`, `PROMPT_SCHEMA_INVALID`, `PROMPT_STALE` |
| Generation | `GENERATION_NOT_READY`, `MODEL_LOAD_FAILED`, `CUDA_OUT_OF_MEMORY`, `SCENE_GENERATION_FAILED` |
| Storage | `PROJECT_NOT_FOUND`, `METADATA_READ_FAILED`, `METADATA_WRITE_FAILED` |
| Config | `OPENAI_API_KEY_MISSING`, `MODEL_ID_MISSING` |

### 15.2 User-Facing Error Rule

Do not show raw stack traces in the UI.

Good:

```text
Your GPU may not have enough memory for this preset. Try Low VRAM Preview or SD 1.5 fallback.
```

Bad:

```text
RuntimeError: CUDA out of memory. Tried to allocate...
```

Stack traces can go to logs in debug mode.

---

## 16. Logging Architecture

Use Python standard `logging`.

### 16.1 Log Locations

Global log:

```text
logs/app.log
```

Project logs:

```text
projects/{project_id}/logs/app.log
projects/{project_id}/logs/generation.log
```

### 16.2 What to Log

Log:

- App startup.
- Project creation.
- Upload validation results.
- OpenAI model used.
- Scene count returned.
- Prompt count returned.
- Hardware profile.
- Model IDs used for generation.
- FaceID enabled/disabled state.
- Per-scene generation success/failure.
- Output filenames.

Do not log:

- OpenAI API key.
- Full raw story content repeatedly.
- Large image binary data.
- Sensitive absolute paths unless debug mode is explicitly enabled.

---

## 17. Security Architecture

### 17.1 Localhost Only

Default server binding:

```text
127.0.0.1
```

Do not expose the app on the local network by default.

### 17.2 Upload Safety

Rules:

- Never trust uploaded filenames as paths.
- Strip directory components from filenames.
- Reject path traversal attempts.
- Validate extensions.
- Validate actual file content.
- Store files only inside the selected project folder.

### 17.3 Markdown Preview Safety

If rendering Markdown preview as HTML:

- Parse Markdown safely.
- Sanitize HTML using `nh3`.
- Use `nh3` for HTML sanitization.
- Do not execute raw HTML or scripts.

### 17.4 OpenAI Privacy Boundary

The app must make clear that story text may be sent to OpenAI when the user runs scene splitting and prompt generation.

Local image generation must not upload generated images or character reference images to a cloud renderer in Phase 1.

---

## 18. Configuration Architecture

Use `.env` and environment variables.

Recommended precedence:

```text
Environment variables
→ .env
→ project generation_settings.json
→ app defaults
```

Secrets must only come from:

```text
Environment variables or .env
```

Never write secrets to:

- `project.json`
- `story.json`
- `scenes.json`
- `prompts.json`
- `generation_settings.json`
- `manifest.json`
- logs

---

## 19. Testing Architecture

Testing should focus on services and schemas first.

Do not require real OpenAI calls or real GPU calls in unit tests.

### 19.1 Unit Tests

Required unit test areas:

- Project folder creation.
- Safe path handling.
- Atomic JSON write/read.
- Story upload validation.
- Story normalization.
- Character filename parsing.
- Character image validation with small test images.
- Duplicate character detection.
- Scene schema validation.
- Prompt schema validation.
- Project state transitions.
- Hardware profile classification using mocked torch data.
- Generation readiness validation.
- Output filename generation.

### 19.2 Integration Tests

Recommended integration tests:

- Create project → upload story → upload character → split scene with mocked OpenAI.
- Approve scene → generate prompt with mocked OpenAI.
- Start generation with mocked GenerationService.
- HTMX progress polling returns expected partial.

### 19.3 Manual Smoke Tests

Manual MVP smoke test:

```text
1. Run setup_windows_gpu.bat or setup_windows_cpu.bat.
2. Run run_windows.bat.
3. Open http://localhost:8000.
4. Create project.
5. Upload story.md.
6. Upload Akira.png.
7. Split scenes.
8. Approve scenes.
9. Generate prompts.
10. Generate one image.
11. Confirm output image and manifest exist.
```

---

## 20. Implementation Order for Codex Agent

Build in this order to reduce mistakes:

```text
1. Project skeleton
2. Config and path utilities
3. JSON file IO with atomic writes
4. Pydantic schemas
5. Project creation flow
6. Story upload and validation
7. Character upload and validation
8. Scene review UI shell
9. Mock scene splitting service
10. Real OpenAI scene splitting
11. Scene edit/reorder/approval
12. Mock prompt generation
13. Real OpenAI prompt generation
14. Hardware detection
15. Generation readiness checks
16. Mock generation job progress
17. Real Diffusers SD 1.5 fallback generation
18. SDXL path
19. IP-Adapter-FaceID hardware-conditional integration
20. Output manifest and retry failed scene behavior
```

Important:

- Build mock paths before real AI calls.
- Do not block UI implementation on GPU setup.
- Do not add advanced architecture to compensate for missing simple services.

---

## 21. Decisions Deferred to Later Docs

This architecture does not fully define:

- Exact endpoint request/response shapes. See `docs/08-api-spec.md`.
- Full Diffusers generation defaults. See `docs/09-generation-pipeline.md`.
- Exact JSON schema details for all files. See `docs/10-data-storage-spec.md`.
- Final project tree and packaging details. See `docs/11-project-structure.md`.
- Full error catalog and logging format. See `docs/12-error-handling-logging.md`.
- Test matrix and coverage rules. See `docs/13-testing-strategy.md`.
- Task-by-task MVP plan. See `docs/14-mvp-task-breakdown.md`.

---

## 22. Architecture Guardrails

Codex Agent must not violate these rules:

1. Keep Phase 1 image-only.
2. Keep the app local-first.
3. Keep the app single-process unless explicitly approved later.
4. Keep the frontend server-rendered with Jinja2 + HTMX.
5. Do not add React or npm build tooling.
6. Do not add a database.
7. Do not add queues or message brokers.
8. Do not add cloud rendering.
9. Do not skip scene review.
10. Do not start generation without approved scenes and valid prompts.
11. Do not expose advanced AI settings in the default UI.
12. Do not promise perfect character identity.
13. Use `IP-Adapter-FaceID` as the selected consistency method when hardware supports it.
14. Persist the consistency method as `ip-adapter-faceid`.
15. Use SD 1.5 fallback for low-VRAM safety.
16. Preserve output order with numeric filename prefixes.
17. Store project-relative paths in metadata.
18. Never store OpenAI API keys in project files.

---

## 23. Final Phase 1 Architecture Definition

Phase 1 architecture is:

```text
A single local Python FastAPI app
serving Jinja2 + HTMX pages at localhost,
using local JSON files for project state,
using OpenAI API only for scene splitting and prompt generation,
using local Diffusers pipelines for image generation,
using IP-Adapter-FaceID only when hardware and dependencies support it,
falling back to SD 1.5 / prompt-only character hints on low-VRAM machines,
and exporting ordered storyboard images into a structured local project folder.
```

This architecture is intentionally boring, simple, and implementation-friendly.
