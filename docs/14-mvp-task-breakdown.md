# 14 — MVP Task Breakdown

**Document:** `docs/14-mvp-task-breakdown.md`  
**Product name:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Status:** Draft based on uploaded docs `00`–`09`  
**Primary user:** Non-technical anime/story creator  

---

## 1. Purpose

This document breaks the Phase 1 MVP into implementation-ready tasks for Codex Agent or another coding agent.

The goal is to make the build sequence clear enough that an agent can implement the app without inventing product scope, architecture, routes, storage behavior, or generation rules.

This task breakdown is based on:

- `docs/00-product-decisions.md`
- `docs/01-prd.md`
- `docs/02-user-flow.md`
- `docs/03-story-input-spec.md`
- `docs/04-character-reference-spec.md`
- `docs/05-scene-splitting-and-prompting-spec.md`
- `docs/06-techstack.md`
- `docs/07-architecture.md`
- `docs/08-api-spec.md`
- `docs/09-generation-pipeline.md`

When implementation details conflict, use this priority order:

```text
1. Product guardrails from docs/00-product-decisions.md and docs/01-prd.md
2. Workflow rules from docs/02-user-flow.md
3. Input and AI behavior specs from docs/03, docs/04, docs/05
4. Architecture rules from docs/07-architecture.md
5. Route contracts from docs/08-api-spec.md
6. Generation behavior from docs/09-generation-pipeline.md
7. This task breakdown
```

---

## 2. Phase 1 MVP Definition

Phase 1 MVP is complete when the app can:

1. Run locally on Windows through a simple startup script.
2. Serve a local FastAPI web UI at `127.0.0.1:8000`.
3. Let the user create a local project.
4. Let the user upload a free-form `.md` story file.
5. Let the user upload character reference images.
6. Validate story and character inputs.
7. Use OpenAI to split the story into ordered scenes.
8. Show the scene list for mandatory user review.
9. Let the user edit, reorder, skip/delete, and approve scenes.
10. Generate prompts only after scene approval.
11. Start image generation only after prompts are valid.
12. Detect hardware and choose a safe generation path.
13. Generate ordered anime storyboard images locally.
14. Save images with numeric filename prefixes.
15. Save generation status and output manifest locally.
16. Show generation progress and final outputs in the UI.

Phase 1 is **not** complete if it bypasses scene review, requires structured story tags, depends on cloud rendering, or only works through a developer-only script without the local web UI.

---

## 3. Hard Guardrails for Every Task

Codex Agent must follow these rules in every task:

1. Do not implement video generation.
2. Do not implement voice generation, lip-sync, subtitles, timeline export, or auto-editing.
3. Do not add accounts, login, OAuth, multi-user cloud behavior, or hosted infrastructure.
4. Do not add React, Next.js, Vue, Vite, npm build tooling, or Tailwind build steps.
5. Do not add PostgreSQL, SQLite, Redis, Celery, Kafka, RabbitMQ, or microservices for Phase 1.
6. Do not bind the app to `0.0.0.0` by default.
7. Do not start image generation unless scenes are approved and prompts are valid.
8. Do not promise perfect character identity.
9. Use `IP-Adapter-FaceID` as the selected character consistency method when hardware supports it.
10. Persist the character consistency method as `ip-adapter-faceid`.
11. Treat 4GB VRAM as low-VRAM mode.
12. Disable IP-Adapter-FaceID by default on low-VRAM mode.
13. Use SD 1.5 fallback or prompt-only hints when SDXL plus FaceID is unsafe.
14. Preserve output order with numeric filename prefixes.
15. Store project-relative paths in metadata.
16. Never store OpenAI API keys in project metadata, prompts, manifests, or logs.
17. Do not silently truncate stories or GPT outputs.
18. Treat all uploaded files and GPT responses as untrusted until validated.

---

## 4. Recommended Build Strategy

Build the app in layers.

Do **not** start with real Diffusers or real OpenAI calls. Build mocks first, wire the workflow, then replace the mock services with real services.

Recommended strategy:

```text
1. Project skeleton and local server
2. Core config, paths, file IO, schemas
3. Project creation and local folder structure
4. Story upload and character upload
5. Scene review UI using mock scene splitting
6. Scene approval and prompt review using mock prompt generation
7. Generation progress using mock generation job
8. Real OpenAI scene splitting
9. Real OpenAI prompt generation
10. Hardware detection and generation readiness
11. Real SD 1.5 fallback generation
12. SDXL path
13. Hardware-conditional IP-Adapter-FaceID
14. Output manifest, retry, polish, tests
```

Reason:

- UI and state gates can be completed before GPU setup is stable.
- Real OpenAI and Diffusers failures become easier to isolate.
- The user can test the complete app flow early with mock outputs.

---

## 5. Milestones Overview

| Milestone | Name | Main Outcome |
|---|---|---|
| M0 | Repository and runtime foundation | App starts locally and renders a home page. |
| M1 | Core infrastructure and metadata foundation | Config, paths, file IO, schemas, and error handling in place. |
| M2 | Project creation and local storage | Projects can be created with safe folders and JSON metadata. |
| M3 | Story input workflow | Story upload is validated and stored. |
| M4 | Character reference workflow | Character images are validated and stored. |
| M5 | Scene workflow with mock AI | User can split, review, edit, reorder, skip, and approve mock scenes. |
| M6 | Prompt workflow with mock AI | User can generate, review, edit, and validate mock prompts. |
| M7 | Generation job shell and mock generation | Generation page, readiness checks, job status, and mock progress work. |
| M8 | Real OpenAI integration | Scene splitting and prompt generation call OpenAI with JSON validation. |
| M9 | Real local image generation | SD 1.5 fallback and SDXL path generate local images. |
| M10 | Character consistency integration | IP-Adapter-FaceID is used only when safe; prompt fallback works. |
| M11 | Output review, manifest, retry, and folder | Manifest, output grid, failed-scene retry, and folder opening are usable. |
| M12 | Logging, error handling, and privacy | Logs exist, secrets are safe, and privacy notice is visible. |
| M13 | Windows setup and developer experience | GPU/CPU setup scripts and run script work on Windows. |
| M14 | Testing and quality gates | Unit tests, integration tests, linting, and smoke test checklist pass. |
| M15 | MVP polish and release readiness | UI copy, scope audit, naming check, and README complete. |

---

## 6. Task ID Convention

Use this task ID format:

```text
M{milestone_number}-T{task_number}
```

Example:

```text
M2-T03 Story upload validation
```

Each implementation pull request or Codex session should reference task IDs in the commit message or summary.

---

# M0 — Repository and Runtime Foundation

## M0-T01 — Create Repository Skeleton

### Goal

Create the initial repository structure required by the architecture and tech stack docs.

### Source Docs

- `docs/06-techstack.md`
- `docs/07-architecture.md`

### Files / Folders

Create:

```text
app/
  main.py
  core/
  web/
  services/
  schemas/
  templates/
    partials/
  static/
    css/
    vendor/htmx/
projects/.gitkeep
logs/.gitkeep
requirements/
scripts/
tests/unit/
tests/integration/
.env.example
README.md
```

### Implementation Notes

- Keep the app single-process.
- Do not add Docker as the only workflow.
- Do not add a frontend build pipeline.

### Acceptance Criteria

- Repository has the expected folders.
- Empty placeholder files do not contain fake business logic.
- `projects/` and `logs/` are present with `.gitkeep`.

### Tests

- No automated test required beyond repository sanity.

---

## M0-T02 — Add Python Dependency Files

### Goal

Create requirements files for base app, AI GPU path, AI CPU path, and dev tools.

### Files

```text
requirements/base.txt
requirements/ai-cu128.txt
requirements/ai-cpu.txt
requirements/dev.txt
```

### Required Base Dependencies

Include Phase 1 web and metadata dependencies:

```text
fastapi
uvicorn[standard]
Jinja2
python-multipart
pydantic
pydantic-settings
python-dotenv
aiofiles
orjson
Pillow
openai
markdown-it-py
nh3
```

### Required Dev Dependencies

```text
pytest
pytest-asyncio
httpx
ruff
mypy
```

### Acceptance Criteria

- Requirements are split by purpose.
- CPU PyTorch install path is separate from CUDA install path.
- No random unofficial `torch` wheel source is hardcoded.

### Tests

- `pip install -r requirements/base.txt -r requirements/dev.txt` works in a clean environment.

---

## M0-T03 — Implement FastAPI App Bootstrap

### Goal

Make the local web app start and render a home page.

### Files

```text
app/main.py
app/web/routes_home.py
app/templates/base.html
app/templates/home.html
app/static/css/app.css
```

### Routes

Implement:

```text
GET /
GET /health
```

### Acceptance Criteria

- App starts with Uvicorn.
- App binds to `127.0.0.1` by default.
- `GET /` returns HTML.
- `GET /health` returns JSON:

```json
{
  "ok": true,
  "status": "healthy",
  "app": "local-ai-anime-storyboard-generator"
}
```

### Tests

- Integration test for `GET /` returns `200`.
- Integration test for `GET /health` returns expected JSON.

---

## M0-T04 — Add Base Templates and HTMX Setup

### Goal

Create the UI foundation with server-rendered pages and local HTMX.

### Files

```text
app/templates/base.html
app/templates/partials/_flash.html
app/static/vendor/htmx/htmx.min.js
app/static/css/app.css
```

### Implementation Notes

- Vendor HTMX locally.
- Do not load HTMX from CDN at runtime.
- Use simple CSS only.

### Acceptance Criteria

- `base.html` includes local CSS and local HTMX.
- Page layout supports flash/error areas.
- No npm or frontend build tool is required.

### Tests

- Template smoke test renders `home.html` without missing includes.

---

# M1 — Core Infrastructure and Metadata Foundation

## M1-T01 — Implement Configuration Layer

### Goal

Create typed app settings loaded from environment variables and `.env`.

### Files

```text
app/core/config.py
.env.example
```

### Required Settings

```text
OPENAI_API_KEY
OPENAI_SCENE_MODEL
OPENAI_PROMPT_MODEL
PROJECTS_ROOT
APP_HOST
APP_PORT
IMAGE_MODEL_ID
LOW_VRAM_IMAGE_MODEL_ID
DEFAULT_OUTPUT_PRESET
ENABLE_IP_ADAPTER_FACEID
FORCE_LOW_VRAM_MODE
LOG_LEVEL
```

### Defaults

Use safe defaults:

```text
APP_HOST=127.0.0.1
APP_PORT=8000
PROJECTS_ROOT=./projects
OPENAI_SCENE_MODEL=gpt-5.4-mini
OPENAI_PROMPT_MODEL=gpt-5.4-mini
DEFAULT_OUTPUT_PRESET=youtube_standard
ENABLE_IP_ADAPTER_FACEID=auto
FORCE_LOW_VRAM_MODE=false
```

### Acceptance Criteria

- Settings load from environment and `.env`.
- Missing OpenAI key does not crash app startup.
- OpenAI key is never logged.

### Tests

- Unit tests for defaults.
- Unit tests for env override.

---

## M1-T02 — Implement Safe Path Utilities

### Goal

Prevent path traversal and keep project file access safe.

### Files

```text
app/core/paths.py
```

### Functions

Implement utilities for:

- Validating `project_id`.
- Building project root path.
- Building metadata path.
- Building input/story path.
- Building character folder path.
- Building outputs/images path.
- Returning project-relative paths for metadata.
- Rejecting `..`, absolute paths, and path separators in unsafe IDs.

### Acceptance Criteria

- All generated paths stay under `PROJECTS_ROOT`.
- Unsafe project IDs are rejected.
- Metadata stores relative paths, not absolute paths.

### Tests

- Valid project ID accepted.
- Path traversal rejected.
- Windows-style separators rejected inside IDs.

---

## M1-T03 — Implement Atomic JSON File IO

### Goal

Create safe helpers for reading and writing JSON metadata.

### Files

```text
app/core/file_io.py
```

### Required Behavior

- Read JSON as UTF-8.
- Write JSON atomically:

```text
write tmp file → flush/close → atomic replace
```

- Create parent folders when needed.
- Compute SHA-256 hashes for text and files.
- Never leave partially written metadata on normal failures.

### Acceptance Criteria

- JSON writes are atomic.
- Helper supports Pydantic model serialization.
- Failed writes do not corrupt existing file when possible.

### Tests

- Unit test for write/read roundtrip.
- Unit test for existing file replacement.
- Unit test for hash generation.

---

## M1-T04 — Implement Error Types and Error Rendering Base

### Goal

Create a consistent error model for services, routes, HTML partials, and JSON responses.

### Files

```text
app/core/errors.py
app/schemas/errors.py
app/templates/partials/_flash.html
```

### Required Shape

JSON errors must support:

```json
{
  "ok": false,
  "error": {
    "code": "STORY_TOO_LARGE",
    "message": "This story file is too large for Phase 1.",
    "details": {}
  }
}
```

### Acceptance Criteria

- App errors have code, message, HTTP status, and details.
- Routes can render errors as HTML partials or JSON.
- Stack traces are not shown to normal users.

### Tests

- Unit test for AppError serialization.
- Integration test for one route validation error.

---

## M1-T05 — Implement Core Pydantic Schemas

### Goal

Create persistent metadata schemas used by services and routes.

### Files

```text
app/schemas/project.py
app/schemas/story.py
app/schemas/character.py
app/schemas/scene.py
app/schemas/prompt.py
app/schemas/generation.py
app/schemas/manifest.py
app/schemas/jobs.py
```

### Required Schema Groups

Implement at least:

- `ProjectMetadata`
- `OutputPreset`
- `StoryMetadata`
- `CharacterMetadata`
- `CharacterReference`
- `SceneList`
- `Scene`
- `PromptList`
- `Prompt`
- `GenerationSettings`
- `HardwareProfile`
- `GenerationJob`
- `OutputManifest`
- `OutputAsset`

### Rules

- Include `version` fields for persisted metadata.
- Use stable enum values.
- Avoid nullable fields unless truly optional.
- Validate persisted consistency method value as `ip-adapter-faceid`.
- Use canonical short preset IDs:

```text
youtube_standard
youtube_high
low_vram_preview
low_vram_tiny
square_preview
vertical_short
```

### Acceptance Criteria

- Schemas validate example metadata from docs.
- Invalid enum values fail validation.
- Project-relative paths are represented as strings.

### Tests

- Unit tests for each schema group.
- Unit tests for preset validation.
- Unit tests for scene and prompt status transitions where modeled.

---

# M2 — Project Creation and Local Storage

## M2-T01 — Implement ProjectService

### Goal

Create local project folders and initial metadata.

### Files

```text
app/services/project_service.py
app/web/routes_projects.py
app/templates/project_new.html
app/templates/project_dashboard.html
```

### Routes

Implement:

```text
GET /projects/new
POST /projects
GET /projects/{project_id}
```

### Created Structure

```text
projects/{project_id}/
  input/
    characters/
  metadata/
    character_cache/
    project.json
    generation_settings.json
  outputs/
    images/
  logs/
```

### Project ID Rule

Generate project IDs as:

```text
slugified-project-name + short-random-suffix
```

Example:

```text
akira-episode-1-a7f3c2
```

### Acceptance Criteria

- User can create a project from UI.
- Project folder is created safely.
- `metadata/project.json` is written.
- `metadata/generation_settings.json` is initialized.
- User is redirected to story upload page.
- Invalid project names show clear errors.

### Tests

- Unit test for project ID generation.
- Unit test for folder creation.
- Integration test for `POST /projects`.

---

## M2-T02 — Implement Project Dashboard State Display

### Goal

Show current project state and the next workflow step.

### Source Docs

- `docs/02-user-flow.md`
- `docs/08-api-spec.md`

### Required Status Values

```text
CREATED
STORY_UPLOADED
CHARACTERS_UPLOADED
SCENES_GENERATED
SCENES_APPROVED
PROMPTS_GENERATED
GENERATION_RUNNING
GENERATION_COMPLETED
STORY_UPLOAD_FAILED
CHARACTER_VALIDATION_FAILED
SCENE_SPLITTING_FAILED
PROMPT_GENERATION_FAILED
GENERATION_FAILED
GENERATION_PARTIAL
```

### Acceptance Criteria

- Dashboard loads project metadata.
- Dashboard shows current step.
- Dashboard links to the correct next page.
- Missing project returns a friendly `PROJECT_NOT_FOUND` error.

### Tests

- Unit test for status-to-next-step mapping.
- Integration test for dashboard route.

---

# M3 — Story Input Workflow

## M3-T01 — Implement StoryService Validation

### Goal

Validate and normalize `.md` story uploads.

### Source Docs

- `docs/03-story-input-spec.md`

### Files

```text
app/services/story_service.py
app/schemas/story.py
```

### Validation Rules

- File is required.
- Extension must be `.md`.
- File must decode as UTF-8.
- UTF-8 BOM is allowed and removed.
- Empty story after trimming is rejected.
- Binary-looking content is rejected.
- File size must be under the Phase 1 limit.
- Normalized text must preserve story order.

### Metadata Output

Write:

```text
projects/{project_id}/input/story.md
projects/{project_id}/metadata/story.json
```

Recommended `story.json` fields:

```text
version
story_status
original_filename
stored_path
file_size_bytes
story_char_count
approx_word_count
line_count
encoding
uploaded_at
content_hash
normalized_line_endings
```

Use `story_char_count`, not ambiguous `character_count`.

### Acceptance Criteria

- Valid `.md` file is saved as `input/story.md`.
- Story metadata is saved.
- Project status becomes `STORY_UPLOADED`.
- Existing scene/prompt/output metadata is marked stale or reset when story changes.
- Invalid files show user-friendly errors.

### Tests

- Unit tests for extension validation.
- Unit tests for UTF-8 decode.
- Unit tests for empty story rejection.
- Unit tests for content hash.

---

## M3-T02 — Implement Story Upload Route and UI

### Files

```text
app/web/routes_story.py
app/templates/story_upload.html
app/templates/partials/_story_validation.html
```

### Routes

Implement:

```text
GET /projects/{project_id}/story
POST /projects/{project_id}/story
```

### UI Requirements

Show:

- Upload area for `.md` file.
- Plain-language explanation that free-form story is accepted.
- File validation status.
- Preview of first part of story.
- Character count and approximate word count.

### Acceptance Criteria

- User can upload story from browser.
- Normal form submit redirects to character upload.
- HTMX submit can render validation partial.
- Errors are shown without raw traceback.

### Tests

- Integration test upload valid story.
- Integration test unsupported file type.
- Integration test empty story.

---

# M4 — Character Reference Workflow

## M4-T01 — Implement CharacterService Validation

### Goal

Validate character reference image files and save character metadata.

### Source Docs

- `docs/04-character-reference-spec.md`

### Files

```text
app/services/character_service.py
app/schemas/character.py
```

### Validation Rules

- At least one image is required for normal flow.
- Accepted extensions:

```text
.png
.jpg
.jpeg
.webp
```

- Unsupported types are rejected.
- Image must decode with Pillow.
- Duplicate filename stems are rejected.
- Filename stem becomes canonical character name.
- Original image is preserved under `input/characters/`.
- Metadata stores project-relative paths.

### Metadata Output

Write:

```text
projects/{project_id}/metadata/characters.json
```

Each character entry should include:

```text
name
original_filename
stored_path
mime_type
width
height
file_size_bytes
is_full_body_expected
consistency_method
status
warnings
```

Persisted consistency method must be:

```text
ip-adapter-faceid
```

### Acceptance Criteria

- Valid images are saved.
- Duplicate character names are blocked.
- Corrupt images are blocked.
- Low-quality images can produce warnings without necessarily blocking.
- Project status can become `CHARACTERS_UPLOADED` when valid refs exist.

### Tests

- Unit test accepted extensions.
- Unit test duplicate stems.
- Unit test corrupt image.
- Unit test metadata creation.

---

## M4-T02 — Implement Character Upload Route and UI

### Files

```text
app/web/routes_characters.py
app/templates/character_upload.html
app/templates/partials/_character_validation.html
```

### Routes

Implement:

```text
GET /projects/{project_id}/characters
POST /projects/{project_id}/characters
DELETE /projects/{project_id}/characters/{character_name}   # optional
```

### UI Requirements

Show:

- Upload area for one or more images.
- Uploaded character list.
- Filename-derived character name.
- Validation status.
- Warnings.
- Reminder: one full-body image per main character.
- Best-effort consistency wording.

### Acceptance Criteria

- User can upload character images.
- UI shows uploaded characters.
- Normal form submit redirects to scenes page.
- HTMX submit renders validation partial.
- Missing/invalid files show plain-language errors.

### Tests

- Integration test valid character upload.
- Integration test duplicate character upload.
- Integration test unsupported extension.

---

# M5 — Scene Workflow with Mock AI

## M5-T01 — Implement Scene Schemas and Scene Metadata Service

### Goal

Manage `metadata/scenes.json` independent of OpenAI.

### Source Docs

- `docs/05-scene-splitting-and-prompting-spec.md`

### Files

```text
app/schemas/scene.py
app/services/scene_service.py
```

### Required Scene Fields

```text
scene_id
scene_number
title
source_excerpt
summary
characters
location
time_of_day
mood
main_action
camera_shot
camera_angle
visual_details
continuity_notes
status
```

### Status Values

```text
draft
approved
needs_edit
skipped
generated
failed
```

### Acceptance Criteria

- Scene list can be loaded and saved.
- Scene order is stable.
- Scene IDs use `scene_001` format.
- Scene numbers are 1-based and sequential for active scenes.
- Skipped scenes are excluded from generation.

### Tests

- Unit test scene validation.
- Unit test renumbering after reorder.
- Unit test skip behavior.

---

## M5-T02 — Implement Mock Scene Splitting Service

### Goal

Allow UI workflow to progress without real OpenAI calls.

### Files

```text
app/services/openai_scene_service.py
```

### Behavior

Before real OpenAI integration, implement a mock mode that:

- Reads `input/story.md`.
- Creates 2–3 deterministic draft scenes.
- Uses uploaded character names when available.
- Saves valid `metadata/scenes.json`.

### Acceptance Criteria

- User can click `Analyze Story and Split Scenes`.
- Draft scenes are created without calling OpenAI when mock mode is enabled.
- Project status becomes `SCENES_GENERATED`.

### Tests

- Unit test mock scene output validates against schema.
- Integration test `POST /projects/{project_id}/scenes/split` with mock service.

---

## M5-T03 — Implement Scene Review Page

### Files

```text
app/web/routes_scenes.py
app/templates/scene_review.html
app/templates/partials/_scene_list.html
app/templates/partials/_scene_card.html
```

### Routes

Implement:

```text
GET /projects/{project_id}/scenes
POST /projects/{project_id}/scenes/split
POST /projects/{project_id}/scenes/{scene_id}
POST /projects/{project_id}/scenes/reorder
POST /projects/{project_id}/scenes/{scene_id}/skip
POST /projects/{project_id}/scenes/approve
```

### UI Requirements

Each scene card shows:

- Scene number.
- Title.
- Summary.
- Source excerpt.
- Characters.
- Location.
- Mood.
- Main action.
- Camera shot and angle.
- Visual details.
- Continuity notes.
- Draft prompt if available later.

### Acceptance Criteria

- User can view draft scenes.
- User can edit scene fields.
- User can reorder scenes.
- User can skip/delete scenes.
- User can approve final scene list.
- App blocks approval when no active scenes exist.
- Approval changes active scenes to `approved`.
- Project status becomes `SCENES_APPROVED`.

### Tests

- Integration test scene update.
- Integration test scene reorder.
- Integration test skip scene.
- Integration test approve scenes.
- Test generation cannot start before approval.

---

# M6 — Prompt Workflow with Mock AI

## M6-T01 — Implement Prompt Schemas and Prompt Metadata Service

### Goal

Manage `metadata/prompts.json` independent of OpenAI.

### Source Docs

- `docs/05-scene-splitting-and-prompting-spec.md`

### Files

```text
app/schemas/prompt.py
app/services/prompt_service.py
```

### Required Prompt Fields

```text
scene_id
scene_number
positive_prompt
negative_prompt
characters
generation_settings
status
manual_edit
```

### Prompt Status Values

Recommended:

```text
ready
stale
failed
```

### Acceptance Criteria

- Prompt list can be loaded and saved.
- Every approved active scene can map to exactly one prompt.
- Stale prompts block generation.
- Manual prompt edits are preserved.

### Tests

- Unit test prompt validation.
- Unit test stale prompt detection.
- Unit test prompt-scene count matching.

---

## M6-T02 — Implement Mock Prompt Generation Service

### Goal

Allow prompt review and generation readiness without OpenAI.

### Files

```text
app/services/openai_prompt_service.py
```

### Behavior

Mock prompt generation should:

- Load approved scenes.
- Create one prompt per approved scene.
- Include anime storyboard style.
- Include character names.
- Include output preset width/height.
- Include default negative prompt.
- Save `metadata/prompts.json`.

### Acceptance Criteria

- Prompts are generated only after scenes are approved.
- Project status becomes `PROMPTS_GENERATED`.
- Prompt route redirects to `/projects/{project_id}/prompts`.

### Tests

- Unit test mock prompt output validates.
- Integration test prompt generation blocked before scene approval.
- Integration test prompt generation succeeds after approval.

---

## M6-T03 — Implement Prompt Review Page

### Files

```text
app/web/routes_prompts.py
app/templates/prompt_review.html
app/templates/partials/_prompt_list.html
app/templates/partials/_prompt_card.html
```

### Routes

Implement:

```text
GET /projects/{project_id}/prompts
POST /projects/{project_id}/prompts/generate
POST /projects/{project_id}/prompts/{scene_id}
POST /projects/{project_id}/prompts/{scene_id}/regenerate   # optional
```

### UI Requirements

- Show approved scenes and prompt status.
- Show generated prompts in an advanced/editable area.
- Let user edit positive and negative prompts.
- Mark manual prompt edits with `manual_edit = true`.
- Do not expose complex diffusion internals in default UI.

### Acceptance Criteria

- User can generate prompts after approval.
- User can edit prompt text.
- Empty prompt text is rejected.
- Manual edits are saved.
- Prompt page links to generation page when prompts are valid.

### Tests

- Integration test update prompt.
- Integration test empty prompt rejected.
- Integration test prompt page renders.

---

# M7 — Generation Job Shell and Mock Generation

## M7-T01 — Implement HardwareService First Pass

### Goal

Detect device and create hardware profile without loading generation models.

### Source Docs

- `docs/06-techstack.md`
- `docs/09-generation-pipeline.md`

### Files

```text
app/services/hardware_service.py
app/schemas/generation.py
```

### Detection Output

Detect:

```text
device
gpu_name
vram_gb
cuda_available
hardware_profile
detected_at
```

`torch_dtype` is not a hardware fact. It is derived from the hardware profile and set in `GenerationPlan` by the generation plan selector. `HardwareService` does not output it.

### Hardware Profiles

```text
cpu_only
low_vram_4gb
mid_vram_6_8gb
high_vram_12gb_plus
unknown
```

### Acceptance Criteria

- CPU-only systems return `cpu_only`.
- CUDA systems return GPU name and VRAM.
- 4GB or below maps to `low_vram_4gb`.
- Hardware detection does not load SDXL.

### Tests

- Unit tests with mocked `torch.cuda` behavior.

---

## M7-T02 — Implement Generation Readiness Gate

### Goal

Block generation unless all prerequisites are valid.

### Source Docs

- `docs/08-api-spec.md`
- `docs/09-generation-pipeline.md`

### Files

```text
app/services/generation_job_service.py
app/services/generation_service.py
```

### Required Checks

- Project exists.
- No job is already running.
- Scenes exist.
- Scenes are approved.
- Prompts exist.
- Prompts are ready.
- Required character references are present.
- Output folder is writable.
- Model config is valid.
- CPU slow warning is acknowledged if needed.
- Low-VRAM warning is surfaced.

### Blocking Error Codes

Implement at least:

```text
PROJECT_NOT_FOUND
GENERATION_ALREADY_RUNNING
SCENE_LIST_NOT_FOUND
SCENE_APPROVAL_REQUIRED
PROMPTS_MISSING
PROMPT_STALE
CHARACTER_REFERENCE_MISSING
OUTPUT_FOLDER_NOT_WRITABLE
MODEL_CONFIG_INVALID
CPU_GENERATION_CONFIRMATION_REQUIRED
```

### Acceptance Criteria

- Backend enforces readiness even if UI buttons are hidden.
- Readiness result includes warnings and blocking errors.
- Generation cannot start before prompts are valid.

### Tests

- Unit tests for each blocking condition.
- Integration test start generation before approval returns error.
- Integration test start generation with valid mock data succeeds.

---

## M7-T03 — Implement Generation Job Status Storage

### Goal

Track generation progress through `metadata/generation_status.json`.

### Files

```text
app/schemas/jobs.py
app/services/generation_job_service.py
```

### Status Values

```text
queued
running
completed
partial
failed
cancel_requested
cancelled
```

### Required Behavior

- Only one job can run at a time.
- Job status is atomically written.
- Status updates after each scene.
- Status includes scene-level results.
- HTMX polling can read current status.

### Acceptance Criteria

- Starting a job creates `generation_status.json`.
- Running job blocks a second job.
- Scene progress is persisted.

### Tests

- Unit test create job.
- Unit test single-job lock.
- Unit test status update.

---

## M7-T04 — Implement Mock Generation Service

### Goal

Complete end-to-end UI flow without real Diffusers.

### Files

```text
app/services/generation_service.py
app/services/manifest_service.py
```

### Behavior

Mock generation should:

- Load approved scenes and ready prompts.
- Create placeholder PNG images with Pillow.
- Save images using numeric filename prefixes.
- Update `generation_status.json` after each scene.
- Write `outputs/manifest.json`.
- Mark project as `GENERATION_COMPLETED` or `GENERATION_PARTIAL`.

### Acceptance Criteria

- User can click Generate Images.
- UI shows progress.
- Placeholder images are saved under `outputs/images/`.
- Filenames follow `{scene_number:03d}_{scene_slug}.png`.
- Manifest links images to scenes.

### Tests

- Integration test complete mock generation flow.
- Unit test output filename slugging.
- Unit test manifest success entry.

---

## M7-T05 — Implement Generation Page and Polling

### Files

```text
app/web/routes_generation.py
app/templates/generation_progress.html
app/templates/partials/_generation_status.html
```

### Routes

Implement:

```text
GET /projects/{project_id}/generation
POST /projects/{project_id}/generation/start
GET /projects/{project_id}/generation/status
POST /projects/{project_id}/generation/cancel          # optional
POST /projects/{project_id}/generation/retry-failed    # later task
```

### HTMX Polling Rule

Render polling trigger only while status is:

```text
queued
running
cancel_requested
```

For terminal statuses, do not render a polling trigger:

```text
completed
partial
failed
cancelled
```

### Acceptance Criteria

- Generation page shows readiness status.
- Start button only appears when ready.
- Backend still enforces readiness.
- Polling updates progress.
- Polling stops on terminal statuses.

### Tests

- Integration test status polling.
- Template test terminal status has no `hx-trigger="every 2s"`.
- Template test running status has polling trigger.

---

# M8 — Real OpenAI Integration

## M8-T01 — Implement OpenAI Client Wrapper

### Goal

Centralize OpenAI calls and keep secrets safe.

### Files

```text
app/services/openai_client.py
app/services/openai_scene_service.py
app/services/openai_prompt_service.py
```

### Rules

- Use official OpenAI Python SDK.
- Read models from config.
- Use JSON/structured output mode where supported.
- Do not log API key.
- Do not save raw full OpenAI request/response content unless debug mode is explicitly enabled.
- Validate responses with Pydantic before saving.

### Acceptance Criteria

- Missing API key returns `OPENAI_API_KEY_MISSING` when action is attempted.
- OpenAI errors map to user-friendly app errors.
- Model ID is configurable.

### Tests

- Unit test missing key behavior.
- Unit test mocked OpenAI success.
- Unit test mocked OpenAI failure.

---

## M8-T02 — Replace Mock Scene Splitting with Real OpenAI Scene Splitting

### Goal

Use OpenAI to split free-form story into ordered scenes.

### Source Docs

- `docs/03-story-input-spec.md`
- `docs/05-scene-splitting-and-prompting-spec.md`

### Required Behavior

- Load normalized story text.
- Load known character names from uploaded filenames.
- Build JSON-only request.
- Do not silently truncate story.
- Estimate token/context risk before sending.
- Save valid draft scenes.
- Surface invalid JSON/schema errors clearly.

### Error Codes

Implement at least:

```text
OPENAI_API_KEY_MISSING
SCENE_SPLIT_FAILED
SCENE_JSON_INVALID
SCENE_SCHEMA_INVALID
STORY_TOO_LARGE_FOR_MODEL
METADATA_WRITE_FAILED
```

### Acceptance Criteria

- Real OpenAI response creates valid `scenes.json`.
- Scene order follows story order.
- Scene status starts as `draft`.
- App still requires user approval.

### Tests

- Unit test with mocked OpenAI JSON response.
- Unit test invalid JSON.
- Unit test schema-invalid scene.
- Integration test route with mocked OpenAI.

---

## M8-T03 — Replace Mock Prompt Generation with Real OpenAI Prompt Generation

### Goal

Use OpenAI to generate image prompts from approved scenes.

### Source Docs

- `docs/05-scene-splitting-and-prompting-spec.md`

### Required Behavior

- Load approved scenes.
- Load character metadata.
- Load output preset.
- Generate one prompt per approved active scene.
- Include positive prompt, negative prompt, character references, and explicit generation settings.
- Save `metadata/prompts.json`.
- Set project status to `PROMPTS_GENERATED`.

### Error Codes

Implement at least:

```text
SCENE_APPROVAL_REQUIRED
OPENAI_API_KEY_MISSING
PROMPT_GENERATION_FAILED
PROMPT_JSON_INVALID
PROMPT_SCHEMA_INVALID
METADATA_WRITE_FAILED
```

### Acceptance Criteria

- Every approved active scene gets one prompt.
- Prompt generation cannot run before scene approval.
- Prompt output references character names consistently.
- Numeric defaults are explicit:

```text
num_images_per_scene = 1
num_inference_steps = 30
guidance_scale = 7.0
```

### Tests

- Unit test mocked prompt response validates.
- Unit test missing scene prompt fails.
- Integration test prompt route with mocked OpenAI.

---

# M9 — Real Local Image Generation

## M9-T01 — Implement Generation Plan Selection

### Goal

Choose SDXL, SD 1.5, CPU, and FaceID modes based on settings and hardware.

### Source Docs

- `docs/09-generation-pipeline.md`

### Inputs

- Hardware profile.
- Generation mode.
- Output preset.
- `IMAGE_MODEL_ID`.
- `LOW_VRAM_IMAGE_MODEL_ID`.
- `ENABLE_IP_ADAPTER_FACEID`.
- `FORCE_LOW_VRAM_MODE`.
- Dependency health checks.

### Required Decisions

- `cpu_only` → SD 1.5 CPU fallback, FaceID disabled.
- `low_vram_4gb` → SD 1.5 fallback, FaceID disabled.
- `mid_vram_6_8gb` → cautious SDXL or fallback, FaceID disabled unless explicitly forced and checks pass.
- `high_vram_12gb_plus` → SDXL, FaceID enabled if dependencies pass.
- `force_low_vram=true` → SD 1.5 fallback, FaceID disabled.

### Acceptance Criteria

- Plan output is persisted in `generation_status.json`.
- Low-VRAM mode never silently attempts SDXL + FaceID.
- Prompt fallback is selected when FaceID is disabled.

### Tests

- Unit tests for each hardware profile.
- Unit test force low-VRAM mode.
- Unit test FaceID unavailable fallback.

---

## M9-T02 — Implement Diffusers Pipeline Factory

### Goal

Load SDXL or SD 1.5 Diffusers pipeline lazily when generation starts.

### Files

```text
app/services/diffusers_pipeline_factory.py
app/services/generation_service.py
```

### Rules

- Do not load models at app startup.
- Use SD 1.5 for low-VRAM fallback.
- Use SDXL when plan selects SDXL.
- Apply safe memory optimizations where supported.
- Do not require xFormers, TensorRT, ONNX conversion, or quantization in MVP.

### Acceptance Criteria

- Pipeline loads only on generation start.
- CPU path uses `float32`.
- CUDA path uses `float16` where safe.
- Model IDs come from config/settings.

### Tests

- Unit tests should mock actual model loading.
- Integration test can use mock pipeline unless CI has GPU.

---

## M9-T03 — Implement Real SD 1.5 Fallback Generation

### Goal

Generate real images locally through SD 1.5 fallback path first.

### Source Docs

- `docs/09-generation-pipeline.md`

### Required Behavior

- Load ready prompts.
- Resolve output size from preset.
- Build runtime prompt package.
- Generate one image per scene by default.
- Save PNG image using numeric filename prefix.
- Update status and manifest after each scene.
- Continue on recoverable per-scene failures unless configured otherwise.

### Acceptance Criteria

- One approved scene can generate a real image locally.
- Low-VRAM preset works with fallback model.
- Generation status updates after scene completion.
- Output manifest records model ID, pipeline, seed, settings, and prompt hashes.

### Tests

- Manual smoke test on CPU or GPU environment.
- Automated tests should mock heavy Diffusers call.

---

## M9-T04 — Implement SDXL Generation Path

### Goal

Add SDXL primary quality path when hardware allows.

### Required Behavior

- Use `IMAGE_MODEL_ID`.
- Respect output preset.
- Apply memory optimizations.
- Fall back or fail gracefully on OOM.
- Record actual pipeline and model used in manifest.

### Acceptance Criteria

- SDXL path can be selected on eligible hardware.
- CUDA OOM is converted into user-friendly error.
- Failed scene is recorded without deleting completed outputs.

### Tests

- Unit tests with mocked SDXL pipeline.
- Manual GPU smoke test where available.

---

# M10 — Character Consistency Integration

## M10-T01 — Implement FaceID Dependency Health Check

### Goal

Check whether IP-Adapter-FaceID dependencies are available without forcing generation startup failure.

### Files

```text
app/services/dependency_service.py
```

### Check

Detect availability of:

- IP-Adapter-FaceID weights or configured path.
- InsightFace.
- ONNX Runtime provider.
- OpenCV if needed.
- Diffusers adapter integration support.

### Acceptance Criteria

- Dependency check returns structured status.
- Missing dependencies produce warnings or fallback decisions.
- Missing dependencies do not crash app startup.

### Tests

- Unit test all dependencies available.
- Unit test missing dependency.

---

## M10-T02 — Implement Runtime Character Reference Resolution

### Goal

Resolve character references per scene/prompt before generation.

### Source Docs

- `docs/04-character-reference-spec.md`
- `docs/05-scene-splitting-and-prompting-spec.md`

### Behavior

For each scene:

- Load prompt characters.
- Match character names to `metadata/characters.json`.
- Resolve `input/characters/{name}.{ext}` safely.
- Build runtime character package.
- If reference is missing and required, block or mark scene failed with clear error.

### Acceptance Criteria

- Character paths are project-relative in metadata.
- Missing required reference does not produce silent prompt-only output unless fallback is explicitly accepted.
- Multi-character scenes are marked best-effort.

### Tests

- Unit test reference resolution.
- Unit test missing character reference.
- Unit test extra uploaded character ignored safely.

---

## M10-T03 — Integrate IP-Adapter-FaceID When Safe

### Goal

Use IP-Adapter-FaceID for character identity guidance only when hardware and dependencies support it.

### Required Behavior

- FaceID is disabled by default on `low_vram_4gb`.
- FaceID is disabled in CPU mode.
- FaceID is enabled only when plan allows and dependencies pass.
- If disabled, final prompt includes prompt-based character hints.
- Manifest records actual runtime consistency mode.

### Persisted Modes

```text
faceid_enabled
faceid_disabled_low_vram
faceid_unavailable
prompt_only
```

### Acceptance Criteria

- The app never claims FaceID was used if it was not.
- Manifest records per-scene character consistency mode.
- Low-VRAM prompt-only fallback works.
- User-facing text says consistency is best-effort.

### Tests

- Unit test low-VRAM disables FaceID.
- Unit test dependency unavailable uses fallback.
- Unit test manifest consistency fields.

---

# M11 — Output Review, Manifest, Retry, and Folder Actions

## M11-T01 — Implement ManifestService Fully

### Goal

Maintain `outputs/manifest.json` for all generation results.

### Source Docs

- `docs/09-generation-pipeline.md`

### Required Fields

Each asset entry should include:

```text
asset_id
job_id
scene_id
scene_number
scene_title
prompt_id
output_filename
output_path
width
height
status
image_model_id
pipeline
seed
num_inference_steps
guidance_scale
output_preset_id
character_references
positive_prompt_hash
negative_prompt_hash
created_at
error_code
error_message
```

### Acceptance Criteria

- Success assets are recorded.
- Failed scenes are recorded with `status = failed`.
- Manifest is updated atomically.
- Manifest stays compact by storing prompt hashes, not full prompt text.

### Tests

- Unit test success entry.
- Unit test failure entry.
- Unit test manifest update does not duplicate same scene/job unexpectedly.

---

## M11-T02 — Implement Output Review Page

### Files

```text
app/web/routes_outputs.py
app/templates/output_review.html
app/templates/partials/_output_grid.html
```

### Routes

Implement:

```text
GET /projects/{project_id}/outputs
GET /projects/{project_id}/outputs/open   # optional but recommended for Windows MVP
```

### UI Requirements

Show:

- Number of successful images.
- Number of failed scenes.
- Output folder path.
- Image preview grid.
- Failed scene list.
- Retry failed scenes button when failures exist.
- Open output folder button when supported.

### Acceptance Criteria

- Output page loads even before generation.
- Generated images display in scene order.
- Failed scenes are visible.
- User can navigate from completed generation to output review.

### Tests

- Integration test output page before generation.
- Integration test output page after mock generation.

---

## M11-T03 — Implement Retry Failed Scenes

### Goal

Allow retrying only failed scenes from a previous generation run.

### Route

```text
POST /projects/{project_id}/generation/retry-failed
```

### Preconditions

- Previous status is `partial` or `failed`.
- Failed scene IDs are known.
- Prompts are still valid.
- No generation job is running.

### Acceptance Criteria

- Retry starts a new job for failed scenes only.
- Successful previous outputs are not deleted.
- New outputs use collision-safe filenames if needed.
- Manifest records retry job separately.

### Tests

- Unit test retry target selection.
- Integration test no failed scenes returns `NO_FAILED_SCENES_TO_RETRY`.
- Integration test retry starts job when failed scenes exist.

---

## M11-T04 — Implement Safe Open Output Folder Action

### Goal

Open the local output folder in Windows Explorer.

### Route

```text
GET /projects/{project_id}/outputs/open
```

### Rules

- Optional for MVP, but useful for non-technical creators.
- Use safe subprocess invocation.
- Do not concatenate unsanitized shell strings.
- Only open the current project output folder.

### Acceptance Criteria

- Button opens `projects/{project_id}/outputs/images` on Windows.
- Non-Windows behavior returns a friendly unsupported message or no-op.
- Missing folder returns `OUTPUT_FOLDER_NOT_FOUND`.

### Tests

- Unit test command construction with mocked subprocess.
- Unit test unsafe project ID rejected.

---

# M12 — Logging, Error Handling, and Privacy

## M12-T01 — Implement Logging Setup

### Goal

Write global and per-project logs without leaking secrets.

### Files

```text
app/core/logging.py
logs/app.log
projects/{project_id}/logs/app.log
projects/{project_id}/logs/generation.log
```

### Log Events

Log:

- Project creation.
- Story validation result.
- Character validation result.
- Scene splitting start/end.
- Prompt generation start/end.
- OpenAI model used.
- Hardware profile.
- Generation plan.
- FaceID enabled/disabled state.
- Per-scene generation success/failure.
- Manifest write result.

Do not log:

- OpenAI API key.
- Full raw story text repeatedly.
- Large image blobs.
- Full absolute paths unless debug mode is enabled.

### Acceptance Criteria

- App log exists.
- Project logs exist after project actions.
- Secrets are not logged.

### Tests

- Unit test API key redaction.
- Integration test generation writes per-project log.

---

## M12-T02 — Add Privacy Notice in UI

### Goal

Tell users that story analysis and prompt generation use OpenAI API.

### UI Locations

Add notice to:

- Story upload or scene splitting screen.
- Prompt generation screen.

### Required Meaning

User-facing copy should explain:

```text
Scene splitting and prompt generation use the OpenAI API. Your story text may be sent for analysis when you run these steps. Image generation runs locally on your machine in Phase 1.
```

### Acceptance Criteria

- Notice is visible before OpenAI scene splitting.
- Notice does not scare users with unnecessary technical jargon.
- Notice does not claim generated images are uploaded to cloud.

### Tests

- Template test checks privacy notice exists on relevant pages.

---

## M12-T03 — Add Markdown Preview Sanitization

### Goal

Prevent unsafe raw HTML execution when previewing story content.

### Files

```text
app/services/story_service.py
app/templates/story_upload.html
```

### Rules

- If rendering Markdown to HTML, sanitize with `nh3`.
- Do not execute raw HTML or scripts.
- Do not fetch remote links or images embedded in Markdown.

### Acceptance Criteria

- Story preview is safe.
- Raw `<script>` in story is escaped or removed.
- Markdown image references are not treated as character references.

### Tests

- Unit test script tag sanitized.
- Unit test Markdown image reference ignored as character upload.

---

# M13 — Windows Setup and Developer Experience

## M13-T01 — Implement Windows GPU Setup Script

### File

```text
scripts/setup_windows_gpu.bat
```

### Responsibilities

1. Check Python version.
2. Create `.venv`.
3. Activate `.venv`.
4. Upgrade `pip`.
5. Install base requirements.
6. Install CUDA PyTorch wheel using official PyTorch index URL.
7. Install GPU AI requirements.
8. Run `scripts/check_gpu.py`.
9. Print next-step instructions.

### Acceptance Criteria

- Script is Windows-first.
- Script does not install unofficial PyTorch wheels.
- Script prints clear failure guidance.

### Tests

- Manual Windows test.

---

## M13-T02 — Implement Windows CPU Setup Script

### File

```text
scripts/setup_windows_cpu.bat
```

### Responsibilities

1. Check Python version.
2. Create `.venv`.
3. Activate `.venv`.
4. Upgrade `pip`.
5. Install base requirements.
6. Install CPU PyTorch wheel using official PyTorch CPU index URL.
7. Install CPU AI requirements.
8. Print warning that CPU generation is slow.

### Acceptance Criteria

- CPU setup path works without NVIDIA GPU.
- User clearly sees CPU generation is slow.

### Tests

- Manual Windows test.

---

## M13-T03 — Implement Run Script

### File

```text
scripts/run_windows.bat
```

### Responsibilities

1. Activate `.venv`.
2. Start FastAPI on `127.0.0.1:8000`.
3. Open browser to `http://localhost:8000`.

### Acceptance Criteria

- Script starts local app.
- App does not bind to public network interfaces by default.
- Browser opens local UI.

### Tests

- Manual Windows smoke test.

---

## M13-T04 — Implement GPU Check Script

### File

```text
scripts/check_gpu.py
```

### Behavior

Print:

- Python version.
- PyTorch version.
- CUDA availability.
- GPU name if available.
- VRAM estimate if available.
- Hardware profile recommendation.

### Acceptance Criteria

- Script works on CPU-only machines.
- Script works on CUDA machines.
- Script does not load SDXL.

### Tests

- Unit test detection function with mocked torch.
- Manual run on available hardware.

---

# M14 — Testing and Quality Gates

## M14-T01 — Add Unit Test Coverage for Core Services

### Goal

Cover critical pure logic and file behavior.

### Required Test Areas

- Config loading.
- Path safety.
- Atomic JSON IO.
- Project creation.
- Story validation.
- Character validation.
- Scene validation and reorder.
- Prompt validation.
- Generation readiness.
- Hardware profile mapping.
- Output filename slugging.
- Manifest updates.

### Acceptance Criteria

- Unit tests run with `pytest`.
- Tests do not require real OpenAI API.
- Tests do not require real GPU.

---

## M14-T02 — Add Integration Tests for Main Workflow

### Goal

Verify the full local web workflow with mocked AI and mocked generation.

### Required Flows

1. Create project → upload story → upload character.
2. Split scenes with mocked OpenAI → approve scenes.
3. Generate prompts with mocked OpenAI.
4. Start mock generation → poll status → view outputs.
5. Attempt generation before approval → blocked.
6. Attempt prompt generation before approval → blocked.
7. Terminal generation status stops HTMX polling.

### Acceptance Criteria

- Integration tests use FastAPI test client or httpx.
- No test calls real OpenAI by default.
- No test loads real Diffusers by default.

---

## M14-T03 — Add Linting, Formatting, and Type Checks

### Goal

Keep code maintainable for agent-driven implementation.

### Tools

```text
ruff
mypy
pytest
```

### Acceptance Criteria

- `ruff check .` passes.
- `ruff format --check .` passes or formatting command is documented.
- `mypy app` passes for core app code.
- `pytest` passes.

---

## M14-T04 — Add Manual MVP Smoke Test Script / Checklist

### Goal

Define a repeatable final manual test.

### Manual Smoke Test

```text
1. Run scripts/setup_windows_gpu.bat or scripts/setup_windows_cpu.bat.
2. Run scripts/run_windows.bat.
3. Open http://localhost:8000.
4. Create a project.
5. Upload story.md.
6. Upload Akira.png.
7. Split scenes.
8. Review and approve scenes.
9. Generate prompts.
10. Open generation page.
11. Start generation.
12. Confirm at least one image is generated.
13. Confirm output filename has numeric prefix.
14. Confirm outputs/manifest.json exists.
15. Confirm output review page shows the generated image.
16. Confirm logs exist.
```

### Acceptance Criteria

- Checklist is included in README or developer docs.
- Smoke test can be followed by a non-expert developer.

---

# M15 — MVP Polish and Release Readiness

## M15-T01 — Review UI Copy for Non-Technical Creator

### Goal

Make the app feel simple and safe for the target user.

### Required Copy Rules

- Do not expose model internals in normal flow.
- Keep advanced settings hidden.
- Use plain-language errors.
- Explain low-VRAM fallback simply.
- Explain character consistency as best-effort.
- Do not promise perfect face preservation.

### Acceptance Criteria

- Story upload, character upload, scene review, prompt review, generation, and output pages have clear text.
- Error messages tell user what to do next.

---

## M15-T02 — Verify Scope Guardrails

### Goal

Ensure MVP did not drift outside Phase 1.

### Checklist

Confirm the codebase does **not** include:

- Video generation.
- Voice generation.
- Lip-sync.
- Subtitle generation.
- Timeline export.
- Account/login system.
- Cloud rendering.
- React or npm build tooling.
- Database dependency.
- External queue/broker dependency.
- LoRA training workflow.
- ComfyUI graph editor.

### Acceptance Criteria

- Scope audit passes.
- Any accidental scope creep is removed or hidden behind non-implemented placeholders.

---

## M15-T03 — Verify Metadata and Preset Naming Consistency

### Goal

Prevent string mismatches across docs and implementation.

### Required Canonical Values

Output presets:

```text
youtube_standard
youtube_high
low_vram_preview
low_vram_tiny
square_preview
vertical_short
```

Character consistency persisted value:

```text
ip-adapter-faceid
```

Project status values:

```text
CREATED
STORY_UPLOADED
CHARACTERS_UPLOADED
SCENES_GENERATED
SCENES_APPROVED
PROMPTS_GENERATED
GENERATION_RUNNING
GENERATION_COMPLETED
STORY_UPLOAD_FAILED
CHARACTER_VALIDATION_FAILED
SCENE_SPLITTING_FAILED
PROMPT_GENERATION_FAILED
GENERATION_FAILED
GENERATION_PARTIAL
```

Generation job statuses:

```text
queued
running
completed
partial
failed
cancel_requested
cancelled
```

### Acceptance Criteria

- No old long preset IDs remain in code.
- No underscore FaceID persisted value remains.
- Tests cover these enum values.

---

## M15-T04 — Final README for Local Run

### Goal

Give the user/developer enough instructions to run the MVP locally.

### README Must Include

- Product name and Phase 1 scope.
- Windows-first setup.
- GPU setup path.
- CPU setup path and slow warning.
- `.env` setup with `OPENAI_API_KEY`.
- How to run app.
- Expected local URL.
- Basic workflow.
- Where outputs are saved.
- Known limitations.

### Acceptance Criteria

- A new developer can follow README to start app.
- README does not call the app a full video generator.

---

## 7. Suggested First Codex Execution Batches

Use these batches to reduce risk.

### Batch 1 — App Skeleton

Tasks:

```text
M0-T01
M0-T02
M0-T03
M0-T04
M1-T01
M1-T02
M1-T03
M1-T04
M1-T05
```

Outcome:

```text
FastAPI app starts, home page works, config/path/file/schema foundation exists.
```

### Batch 2 — Project + Input Flow

Tasks:

```text
M2-T01
M2-T02
M3-T01
M3-T02
M4-T01
M4-T02
```

Outcome:

```text
User can create project, upload story, upload character images, and save metadata.
```

### Batch 3 — Review Workflow with Mocks

Tasks:

```text
M5-T01
M5-T02
M5-T03
M6-T01
M6-T02
M6-T03
```

Outcome:

```text
End-to-end scene and prompt workflow works without real OpenAI.
```

### Batch 4 — Mock Generation End-to-End

Tasks:

```text
M7-T01
M7-T02
M7-T03
M7-T04
M7-T05
M11-T01
M11-T02
```

Outcome:

```text
Full MVP workflow works end-to-end — mock images generated, manifest written, output review page functional.
```

### Batch 5 — Real AI Integrations

Tasks:

```text
M8-T01
M8-T02
M8-T03
M9-T01
M9-T02
M9-T03
M9-T04
M10-T01
M10-T02
M10-T03
```

Outcome:

```text
OpenAI scene/prompt generation and local Diffusers image generation work.
```

### Batch 6 — Release Hardening

Tasks:

```text
M11-T03
M11-T04
M12-T01
M12-T02
M12-T03
M13-T01
M13-T02
M13-T03
M13-T04
M14-T01
M14-T02
M14-T03
M14-T04
M15-T01
M15-T02
M15-T03
M15-T04
```

Outcome:

```text
MVP is testable, usable on Windows, and ready for local creator workflow validation.
```

---

## 8. MVP Cut Line

If time is limited, the minimum credible MVP cut is:

### Must Have

- Local FastAPI + Jinja2 + HTMX app.
- Project creation.
- Story upload validation.
- Character upload validation.
- Scene splitting with OpenAI.
- Mandatory scene review and approval.
- Prompt generation with OpenAI.
- Generation readiness gates.
- At least SD 1.5 local generation path.
- Ordered PNG outputs.
- Manifest.
- Output review page.
- Windows run script.

### Can Ship Slightly Later

- SDXL path polish.
- IP-Adapter-FaceID full integration.
- Retry failed scenes.
- Open output folder button.
- Advanced prompt editing.
- Cancellation.
- Better project history / open existing project list.
- Image upscaling.

### Must Not Be Cut

These cannot be removed from MVP:

- Scene review before generation.
- Ordered output filenames.
- Local output folder.
- Story `.md` upload.
- Character image upload.
- Clear low-VRAM fallback behavior.
- No video generation in Phase 1.

---

## 9. Final MVP Acceptance Checklist

The MVP is accepted only when all statements below are true:

```text
[ ] App starts locally on Windows.
[ ] App serves UI at 127.0.0.1:8000 or localhost.
[ ] User can create a project.
[ ] Project folder structure is created correctly.
[ ] User can upload a free-form .md story.
[ ] User can upload character reference images.
[ ] Character filenames map to character names.
[ ] OpenAI scene splitting creates ordered draft scenes.
[ ] User can review scenes before generation.
[ ] User can edit scenes.
[ ] User can reorder scenes.
[ ] User can skip/delete scenes.
[ ] User must approve scenes before prompt generation.
[ ] Prompt generation creates one prompt per approved active scene.
[ ] Generation cannot start if scenes are not approved.
[ ] Generation cannot start if prompts are missing or stale.
[ ] Hardware detection identifies CPU/GPU and low-VRAM profile.
[ ] 4GB VRAM uses safe low-VRAM behavior.
[ ] SD 1.5 fallback works.
[ ] SDXL path works when hardware allows, or fails gracefully.
[ ] IP-Adapter-FaceID is enabled only when safe.
[ ] Prompt-only fallback works when FaceID is disabled.
[ ] Generated images are saved under outputs/images.
[ ] Generated image filenames use numeric prefixes.
[ ] outputs/manifest.json records results.
[ ] generation_status.json updates during generation.
[ ] Output review page shows generated images.
[ ] Errors are user-friendly.
[ ] Logs exist and do not leak API keys.
[ ] Tests pass.
[ ] README explains setup and workflow.
```

---

## 10. Final Instruction for Codex Agent

Implement this MVP from foundation to AI integration.

Do not skip ahead to real Diffusers before the local web workflow works with mocks.

Do not add architecture that is not required by the docs.

Keep every task small, testable, and aligned with the confirmed Phase 1 product rules.
