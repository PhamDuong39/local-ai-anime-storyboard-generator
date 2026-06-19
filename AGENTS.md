# AGENTS.md — Codex Implementation Guide

**Project:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Primary agent:** Codex Agent / coding agent  
**Primary user:** Non-technical anime/story creator  
**Runtime target:** Windows-first local web app  
**Last updated:** 2026-06-11

---

## 1. Purpose

This file tells Codex Agent how to implement the Phase 1 MVP without reopening product decisions, changing architecture, or drifting into unsupported scope.

Use this file as the first implementation control document for every coding session.

The MVP is a local AI anime storyboard/image generator. The user uploads a free-form Markdown story and one full-body reference image per main character, reviews an auto-generated scene list, then generates ordered anime storyboard images locally.

Phase 1 is **image-only**. It is not a full video generator.

---

## 2. Source-of-Truth Documents

Before implementing any task, read the relevant docs in this order.

### 2.1 Priority Order

When documents conflict, follow this priority order:

```text
1. docs/00-product-decisions.md and docs/01-prd.md
2. docs/02-user-flow.md
3. docs/03-story-input-spec.md
4. docs/04-character-reference-spec.md
5. docs/05-scene-splitting-and-prompting-spec.md
6. docs/06-techstack.md
7. docs/07-architecture.md
8. docs/08-api-spec.md
9. docs/09-generation-pipeline.md
10. docs/14-mvp-task-breakdown.md
11. AGENTS.md
```

`AGENTS.md` controls how to work, but it does not override product, workflow, architecture, API, or generation specs.

### 2.2 Current Available Docs

The current implementation baseline includes:

```text
docs/00-product-decisions.md
docs/01-prd.md
docs/02-user-flow.md
docs/03-story-input-spec.md
docs/04-character-reference-spec.md
docs/05-scene-splitting-and-prompting-spec.md
docs/06-techstack.md
docs/07-architecture.md
docs/08-api-spec.md
docs/09-generation-pipeline.md
docs/14-mvp-task-breakdown.md
```

Some recommended future docs may not exist yet:

```text
docs/10-data-storage-spec.md
docs/11-project-structure.md
docs/12-error-handling-logging.md
docs/13-testing-strategy.md
```

If a future doc is missing, do not invent large new systems. Use the already available docs and keep the implementation boring, local, JSON-file based, and MVP-focused.

---

## 3. Phase 1 Definition

Phase 1 is complete when the app can:

1. Run locally on Windows with simple setup and run scripts.
2. Serve a FastAPI web UI at `127.0.0.1:8000`.
3. Let the user create a local project.
4. Let the user upload one free-form `.md` story file.
5. Let the user upload character reference images.
6. Validate story and character inputs.
7. Use OpenAI to split the story into ordered scenes.
8. Show the scene list for mandatory review.
9. Let the user edit, reorder, skip/delete, and approve scenes.
10. Generate prompts only after scene approval.
11. Start image generation only after prompts are valid.
12. Detect hardware and choose a safe generation path.
13. Generate ordered anime storyboard images locally.
14. Save images with numeric filename prefixes.
15. Save generation status and output manifest locally.
16. Show generation progress and final outputs in the UI.

Phase 1 is not complete if it bypasses scene review, requires structured story tags, depends on cloud rendering, or only works through a developer-only script without the local web UI.

---

## 4. Hard Guardrails

Codex Agent must follow these rules in every task.

### 4.1 Product Scope Guardrails

Do not implement:

- Video generation.
- Voice generation.
- Voice cloning.
- Lip-sync.
- Subtitle generation.
- Auto-editing full videos.
- Timeline export for CapCut, Premiere, DaVinci Resolve, or similar tools.
- Multi-user cloud server.
- Account system.
- Authentication or OAuth.
- Public sharing.
- Payment flows.
- Cloud rendering.
- Real-time collaborative editing.
- Advanced character LoRA training.
- DreamBooth training.
- ComfyUI graph editing.

### 4.2 Architecture Guardrails

Do not add:

- React.
- Next.js.
- Vue.
- Svelte.
- Vite.
- Webpack.
- Tailwind build pipeline.
- npm-required frontend build tooling.
- PostgreSQL.
- MySQL.
- MongoDB.
- Redis.
- SQLite as required project storage.
- Kafka.
- RabbitMQ.
- Celery.
- Microservices.
- Kubernetes.
- Docker-only workflow.

Docker may be added later as optional developer convenience only if explicitly approved. SQLite may be considered later, but Phase 1 uses local folders and JSON files.

### 4.3 Workflow Guardrails

Never start image generation unless all are true:

1. Story exists and is valid.
2. Character metadata exists and is valid enough for the selected flow.
3. Scenes exist.
4. User explicitly approved scenes.
5. Prompts exist.
6. Prompts are valid and not stale.
7. No generation job is already running.
8. Output folder is writable.
9. Model configuration is valid.
10. Hardware warnings that require acknowledgement have been handled.

The UI hiding a button is not enough. Backend services must enforce state gates.

### 4.4 AI and Character Guardrails

- Use OpenAI only for story understanding, scene splitting, scene summarization, prompt generation, and prompt enrichment.
- Use local Diffusers pipelines for image generation.
- Use `IP-Adapter-FaceID` as the selected character consistency approach when hardware and dependencies support it.
- Persist the character consistency method as `ip-adapter-faceid` in JSON/config/manifest files.
- Do not use persisted variants like `ip_adapter_faceid`.
- Character consistency is best effort.
- Do not promise perfect face preservation.
- Do not promise identical outfits in every image.
- On 4GB VRAM machines, treat the machine as low-VRAM mode.
- On low-VRAM mode, disable IP-Adapter-FaceID by default and use SD 1.5 fallback or prompt-based character hints.
- Do not silently attempt SDXL plus IP-Adapter-FaceID on 4GB VRAM.
- On mid_vram_6_8gb machines, disable IP-Adapter-FaceID by default.
  Enable only when ENABLE_IP_ADAPTER_FACEID is explicitly set to force
  and all dependency checks pass.

### 4.5 Security and Privacy Guardrails

- Never store `OPENAI_API_KEY` in project metadata, prompts, manifests, logs, screenshots, or generated outputs.
- Never log secrets.
- Never show raw stack traces to normal users.
- Treat uploaded files as untrusted.
- Treat GPT responses as untrusted until Pydantic validation passes.
- Sanitize rendered Markdown preview with `nh3` if rendering Markdown as HTML.
- Do not execute raw HTML from uploaded story files.
- Do not fetch remote URLs or remote images referenced inside Markdown.
- Do not trust uploaded filenames as paths.
- Store project-relative paths in metadata whenever possible.
- Reject path traversal attempts.

---

## 5. Canonical Technical Decisions

### 5.1 Runtime

Use:

```text
Python 3.12.x 64-bit
FastAPI
Uvicorn
Jinja2
HTMX
Plain CSS
Pydantic v2
Local JSON files
PyTorch
Diffusers
Pillow
OpenAI Python SDK
```

Default local server:

```text
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Do not bind to `0.0.0.0` by default.

### 5.2 OpenAI

Use environment variables:

```env
OPENAI_API_KEY=...
OPENAI_SCENE_MODEL=gpt-5.4-mini
OPENAI_PROMPT_MODEL=gpt-5.4-mini
```

OpenAI responses for scene splitting and prompt generation must use JSON response mode or structured output where supported by the current SDK.

All OpenAI output must be schema-validated before saving as trusted metadata.

### 5.3 Output Preset IDs

Use canonical short preset IDs only:

```text
youtube_standard
youtube_high
low_vram_preview
low_vram_tiny
square_preview
vertical_short
```

Default:

```text
youtube_standard
```

Do not introduce older long IDs like:

```text
youtube_standard_720p
youtube_high_1080p
low_vram_preview_540p
square_preview_1024
vertical_short_1080x1920
```

unless updating legacy data through an explicit migration or compatibility adapter.

### 5.4 Character Consistency Naming

Human-readable UI/docs name:

```text
IP-Adapter-FaceID
```

Persisted JSON/config/manifest value:

```text
ip-adapter-faceid
```

### 5.5 Hardware Profiles

Use these profile values:

```text
cpu_only
low_vram_4gb
mid_vram_6_8gb
high_vram_12gb_plus
unknown
```

4GB VRAM or below maps to:

```text
low_vram_4gb
```

---

## 6. Repository Structure

Create and maintain this repository structure unless a later source-of-truth doc explicitly changes it.

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
      scene_service.py
      prompt_service.py
      openai_scene_service.py
      openai_prompt_service.py
      hardware_service.py
      generation_service.py
      generation_job_service.py
      manifest_service.py
      dependency_service.py
      pipeline_factory.py
      openai_client.py
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
      project_new.html
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
        _scene_list.html
        _scene_card.html
        _prompt_list.html
        _prompt_card.html
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
  AGENTS.md
```

Do not put all routes in `main.py`. Keep business logic in services, not routes.

---

## 7. Project Folder Structure

Every local project must use this structure:

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

Rules:

- Store project-relative paths in metadata.
- Use atomic JSON writes.
- Include `version` fields in persisted metadata files.
- Never write partial/corrupt metadata on normal failures.
- Output filenames must preserve approved scene order with numeric prefixes.

---

## 8. Implementation Strategy

Build mocks first, then real integrations.

Recommended order:

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

Important:

- Do not block UI/state-gate implementation on GPU setup.
- Do not call real OpenAI in default unit tests.
- Do not load real Diffusers models in default unit tests.
- Do not implement real AI before mock workflow is passing end to end.

---

## 9. Milestone Plan

Use task IDs from `docs/14-mvp-task-breakdown.md`.

```text
M0  Repository and runtime foundation
M1  Core infrastructure and metadata foundation
M2  Project creation and local storage
M3  Story input workflow
M4  Character reference workflow
M5  Scene workflow with mock AI
M6  Prompt workflow with mock AI
M7  Generation job shell and mock generation
M8  Real OpenAI integration
M9  Real local image generation
M10 Character consistency integration
M11 Output review, manifest, retry, and folder
M12 Logging, error handling, and privacy
M13 Windows setup and developer experience
M14 Testing and quality gates
M15 MVP polish and release readiness
```

Every Codex session should state which task ID it is implementing.

Commit summaries should include task IDs when possible.

Example:

```text
M3-T01 implement story upload validation
```

---

## 10. Route Implementation Rules

Follow `docs/08-api-spec.md` for route contracts.

### 10.1 Endpoint Priority

Implement endpoints in this order:

```text
1. GET /health
2. GET /
3. GET /projects/new
4. POST /projects
5. GET /projects/{project_id}
6. GET /projects/{project_id}/story
7. POST /projects/{project_id}/story
8. GET /projects/{project_id}/characters
9. POST /projects/{project_id}/characters
10. GET /projects/{project_id}/scenes
11. POST /projects/{project_id}/scenes/split with mocked OpenAI first
12. POST /projects/{project_id}/scenes/{scene_id}
13. POST /projects/{project_id}/scenes/reorder
14. POST /projects/{project_id}/scenes/{scene_id}/skip
15. POST /projects/{project_id}/scenes/approve
16. GET /projects/{project_id}/prompts
17. POST /projects/{project_id}/prompts/generate with mocked OpenAI first
18. POST /projects/{project_id}/prompts/{scene_id}
19. GET /projects/{project_id}/generation
20. POST /projects/{project_id}/generation/start with mocked generation first
21. GET /projects/{project_id}/generation/status
22. GET /projects/{project_id}/outputs
23. Optional retry/cancel/open-folder routes
```

### 10.2 Response Mode Rules

Use:

- Full HTML pages for normal navigation.
- HTMX partials for form submit results, scene cards, validation, and generation polling.
- JSON only where useful for status polling, tests, or debug-friendly routes.
- `303 See Other` for successful normal form transitions.

For HTMX requests, detect:

```text
HX-Request: true
```

Do not create a separate public `/api/v1` REST layer in Phase 1.

### 10.3 API Out-of-Scope Routes

Do not add:

- Login routes.
- Admin routes.
- Cloud sync routes.
- Payment routes.
- Public sharing routes.
- Video generation routes.
- Audio generation routes.
- Subtitle routes.
- Timeline export routes.
- GraphQL.
- WebSocket API unless explicitly approved later.

---

## 11. State Machine Rules

Use these project status values:

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

Normal flow:

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

Never allow:

```text
SCENES_GENERATED → GENERATION_RUNNING
```

Prompt generation requires approved scenes. Image generation requires approved scenes and ready prompts.

---

## 12. Story Input Rules

Story input is a free-form Markdown file.

Supported extension:

```text
.md
```

Do not require:

- Scene tags.
- Character tags.
- YAML front matter.
- JSON.
- Prompt syntax.
- Screenplay formatting.

Validation rules:

- File is required.
- Extension must be `.md`.
- File must decode as UTF-8.
- UTF-8 BOM is allowed and removed.
- Empty story after trimming is rejected.
- Binary-looking content is rejected.
- File size must be under the Phase 1 limit.
- Text order must be preserved.

Store uploaded story as:

```text
projects/{project_id}/input/story.md
```

Store metadata as:

```text
projects/{project_id}/metadata/story.json
```

Use field name:

```text
story_char_count
```

Do not use ambiguous `character_count` for story text length.

---

## 13. Character Reference Rules

Supported image extensions:

```text
.png
.jpg
.jpeg
.webp
```

Each main character must have exactly one uploaded reference image in Phase 1.

The filename stem is the canonical character name.

Example:

```text
Akira.png → Akira
Hana.jpg → Hana
Yuki.webp → Yuki
```

Rules:

- One character equals one reference image.
- Character image should be full-body.
- Character image should show face, body, outfit, and anime style.
- Filename should match the story character name.
- Reject duplicate filename stems.
- Reject corrupt images.
- Store originals under `input/characters/`.
- Store metadata in `metadata/characters.json`.
- Do not implement in-app character LoRA training.
- Do not implement per-scene outfit changes in Phase 1.

Best-effort wording is required.

Allowed wording:

```text
The app will try to preserve the character's face, outfit, and visual identity using the uploaded reference image.
```

Forbidden wording:

```text
The face will never change.
The character will be perfectly identical in every image.
```

---

## 14. Scene Splitting Rules

Scene splitting uses GPT.

The splitter must:

- Accept free-form story text.
- Preserve story order.
- Infer scenes from prose, dialogue, action, location changes, emotional beats, and visual moments.
- Produce JSON only.
- Use stable scene IDs like `scene_001`.
- Use 1-based scene numbers.
- Save draft scenes to `metadata/scenes.json`.
- Show scenes to the user before any generation.

Every scene must include at least:

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

Allowed scene status values:

```text
draft
approved
needs_edit
skipped
generated
failed
```

GPT output starts as:

```text
draft
```

User approval changes active scenes to:

```text
approved
```

Skipped scenes must not be generated.

Do not silently truncate stories or GPT responses.

---

## 15. Prompt Generation Rules

Prompt generation starts only after scene approval.

Allowed flow:

```text
GPT splits scenes → user reviews scenes → user approves scenes → app generates prompts
```

Disallowed flow:

```text
GPT splits scenes → app immediately generates images
```

Prompts must be saved to:

```text
projects/{project_id}/metadata/prompts.json
```

Each approved active scene must map to exactly one prompt.

Prompt status values:

```text
ready
stale
failed
```

Stale prompts block generation.

Default numeric generation settings must be explicit:

```text
num_images_per_scene = 1
num_inference_steps = 30
guidance_scale = 7.0
```

Final prompts must avoid:

- Speech bubbles.
- Subtitles.
- Readable text in image.
- Video terms.
- Lip-sync terms.
- Timeline instructions.
- Watermarks or logos.

---

## 16. Generation Rules

Image generation runs locally with Diffusers.

Primary path:

```text
SDXL
```

Low-VRAM fallback:

```text
SD 1.5
```

Default model environment variables:

```env
IMAGE_MODEL_ID=stabilityai/stable-diffusion-xl-base-1.0
LOW_VRAM_IMAGE_MODEL_ID=stable-diffusion-v1-5/stable-diffusion-v1-5
```

Model IDs must be configurable and stored in generation metadata/manifest.

### 16.1 Readiness Gate

Before creating a generation job, check:

```text
PROJECT_NOT_FOUND
GENERATION_ALREADY_RUNNING
SCENE_LIST_NOT_FOUND
SCENE_APPROVAL_REQUIRED
PROMPTS_MISSING
PROMPT_STALE
PROMPT_SCHEMA_INVALID
CHARACTER_REFERENCE_MISSING
OUTPUT_FOLDER_NOT_WRITABLE
MODEL_CONFIG_INVALID
CPU_GENERATION_CONFIRMATION_REQUIRED
```

If any blocking error exists, do not start generation.

### 16.2 Job Concurrency

Only one generation job should run at a time per local app process.

Recommended implementation:

```text
ThreadPoolExecutor(max_workers=1)
```

Do not add Celery, Redis, queues, or broker systems.

### 16.3 Model Loading

Do not load SDXL, SD 1.5, IP-Adapter, FaceID dependencies, or large model weights at app startup.

Load generation models lazily when a generation job starts.

### 16.4 Scene Execution

Generate scenes one by one.

Do not batch multiple scenes in Phase 1.

Each scene should:

1. Load scene metadata.
2. Load matching prompt.
3. Resolve character references.
4. Build final runtime prompt package.
5. Select runtime consistency mode.
6. Generate one image by default.
7. Save output file with numeric prefix.
8. Update `generation_status.json`.
9. Update `outputs/manifest.json`.
10. Log success/failure.

---

## 17. Output Rules

Generated images must be saved to:

```text
projects/{project_id}/outputs/images/
```

Filename format:

```text
{scene_number:03d}_{scene_slug}.png
```

Examples:

```text
001_akira_enters_school.png
002_hana_warning.png
003_dark_hallway.png
```

Slug rules:

- Lowercase.
- ASCII-safe if practical.
- Replace spaces with underscores.
- Remove unsafe path characters.
- Max recommended slug length: 60 characters.
- If empty, use `scene`.
- Never use raw user text directly as a path.

Default overwrite behavior:

```text
overwrite_existing_outputs = false
```

If a file exists, create versioned names:

```text
001_akira_enters_school_v2.png
001_akira_enters_school_v3.png
```

Every generation result must be recorded in:

```text
projects/{project_id}/outputs/manifest.json
```

---

## 18. Error Handling Rules

Use consistent app errors with:

```text
code
message
http_status
details
```

JSON error shape:

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

Rules:

- User-facing messages should explain what the user can do next.
- Do not expose raw stack traces.
- Do not expose secrets.
- Do not expose absolute paths unless debug mode explicitly allows it.
- For HTMX requests, render an error partial.
- For normal page requests, render a page with an error banner.
- For JSON routes, return the standard error shape.

---

## 19. Logging Rules

Use Python logging.

Required logs:

```text
logs/app.log
projects/{project_id}/logs/app.log
projects/{project_id}/logs/generation.log
```

Rules:

- Never log OpenAI API keys.
- Redact secrets from exceptions/config dumps.
- Log model IDs used, but not secrets.
- Log hardware profile decisions.
- Log low-VRAM fallback decisions.
- Log per-scene generation success/failure.
- Keep user-facing errors friendly; keep technical details in logs.

---

## 20. Testing Rules

Default tests must not require:

- Real OpenAI API calls.
- Real GPU.
- Real Diffusers model loading.
- Internet access.

Use mocks/fakes for:

- OpenAI scene splitting.
- OpenAI prompt generation.
- Diffusers generation.
- CUDA hardware detection.

Required test areas:

- Config loading.
- Path safety.
- Atomic JSON IO.
- Project creation.
- Story validation.
- Markdown preview sanitization.
- Character image validation.
- Filename-to-character mapping.
- Scene JSON validation.
- Scene reorder/skip/approval.
- Prompt JSON validation.
- Stale prompt blocking.
- Generation readiness.
- Hardware profile mapping.
- Output filename ordering.
- Manifest updates.
- HTMX terminal generation status stops polling.

Use:

```text
pytest
pytest-asyncio
httpx
ruff
mypy
```

Ruff should handle formatting, import sorting, and linting.

Mypy should be strict for schemas, services, path handling, OpenAI parsing, and generation config models.

---

## 21. Windows Setup Rules

Windows is the first target OS.

Required scripts:

```text
scripts/setup_windows_gpu.bat
scripts/setup_windows_cpu.bat
scripts/run_windows.bat
scripts/check_gpu.py
```

### 21.1 GPU Setup Script

`setup_windows_gpu.bat` should:

1. Check Python version.
2. Create `.venv`.
3. Activate `.venv`.
4. Upgrade `pip`.
5. Install base requirements.
6. Install CUDA PyTorch wheel using the official PyTorch index URL.
7. Install GPU AI requirements.
8. Run `scripts/check_gpu.py`.
9. Print next-step instructions.

Do not install unofficial PyTorch wheels.

### 21.2 CPU Setup Script

`setup_windows_cpu.bat` should:

1. Check Python version.
2. Create `.venv`.
3. Activate `.venv`.
4. Upgrade `pip`.
5. Install base requirements.
6. Install CPU PyTorch wheel using the official PyTorch CPU index URL.
7. Install CPU AI requirements.
8. Print warning that CPU generation is slow.

### 21.3 Run Script

`run_windows.bat` should:

1. Activate `.venv`.
2. Start FastAPI on `127.0.0.1:8000`.
3. Open browser to `http://localhost:8000`.

---

## 22. Codex Working Protocol

For every coding task, Codex Agent should:

1. Identify the milestone/task ID from `docs/14-mvp-task-breakdown.md`.
2. Read the relevant source docs before editing.
3. State the files it plans to modify.
4. Keep changes small and task-focused.
5. Prefer simple service-layer logic over route-level business logic.
6. Add or update tests for changed behavior.
7. Run relevant tests when possible.
8. Run formatting/linting/type checks when possible.
9. Summarize what changed and what was not changed.
10. Mention any unresolved doc conflict or blocked dependency.

Codex must not:

- Invent product features outside the task.
- Add dependencies without checking `docs/06-techstack.md`.
- Skip tests because a feature uses AI.
- Replace server-rendered UI with a frontend app.
- Move project state into a database.
- Add hidden cloud behavior.
- Store secrets in files.

---

## 23. Dependency Rules

Before adding a dependency:

1. Check `docs/06-techstack.md`.
2. Confirm it is needed for the current task.
3. Prefer standard library or existing project dependency if reasonable.
4. Add it to the correct requirements file.
5. Avoid dependencies that require npm or frontend builds.
6. Avoid dependencies that are fragile on Windows unless they are already part of the AI stack decision.

Core dependency groups:

```text
requirements/base.txt       web app, validation, local metadata, OpenAI client
requirements/ai-cu128.txt   CUDA AI packages, GPU generation path
requirements/ai-cpu.txt     CPU AI packages, CPU fallback path
requirements/dev.txt        tests, linting, type checking
```

Do not install arbitrary PyTorch wheels from random sources. Use official PyTorch index URLs.

---

## 24. Documentation Update Rules

When code changes behavior that affects docs:

1. Update the relevant doc in the same task if the doc exists.
2. Keep terminology consistent.
3. Use `ip-adapter-faceid` for persisted values.
4. Use short preset IDs.
5. Keep Phase 1 positioned as storyboard/image generation only.
6. Do not add video-generator wording to user-facing docs.

If a doc conflict is discovered, do not silently choose a third option. Follow the priority order in Section 2 and note the conflict in the task summary.

---

## 25. MVP Smoke Test

Before claiming MVP flow works, run or simulate this smoke test with mocked AI/generation first:

```text
1. Run setup script or install base dependencies.
2. Run scripts/run_windows.bat or equivalent local command.
3. Open http://localhost:8000.
4. Create a project.
5. Upload story.md.
6. Upload Akira.png.
7. Split scenes.
8. Review scenes.
9. Edit/reorder/skip if needed.
10. Approve scenes.
11. Generate prompts.
12. Start mock generation.
13. Poll generation status.
14. Confirm ordered output files exist.
15. Confirm outputs/manifest.json exists.
16. Confirm generation_status.json reaches terminal state.
17. Confirm terminal state stops HTMX polling.
```

Then test real OpenAI and real Diffusers paths separately.

---

## 26. Final Implementation North Star

The Phase 1 app should stay simple:

```text
A single local Python FastAPI app
serving Jinja2 + HTMX pages at 127.0.0.1:8000,
using local JSON files for project state,
using OpenAI API only for scene splitting and prompt generation,
using local Diffusers pipelines for image generation,
using IP-Adapter-FaceID only when hardware and dependencies support it,
falling back to SD 1.5 / prompt-only character hints on low-VRAM machines,
and exporting ordered storyboard images into a structured local project folder.
```

If a proposed change makes the app more like a cloud platform, a full video generator, a microservice architecture, or an AI engineering dashboard, do not implement it in Phase 1 without explicit product approval.
