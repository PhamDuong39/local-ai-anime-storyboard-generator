# Local AI Anime Storyboard Generator — API Specification

**Document:** `docs/08-api-spec.md`  
**Product name:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Status:** Draft based on confirmed docs `00`–`07`  
**Primary user:** Non-technical anime/story creator  

---

## 1. Purpose

This document defines the HTTP route contract for the Phase 1 local web app.

The goal is to make the app easy for Codex Agent to implement without inventing route names, request shapes, response shapes, or state rules.

Phase 1 uses:

```text
FastAPI + Jinja2 + HTMX
```

This is not a public cloud REST API. The routes are primarily local UI routes and HTMX action routes running on the user's own machine.

The app must stay:

- Local-first.
- Windows-first.
- Single-user.
- Image-only.
- Server-rendered.
- JSON-file based.
- Simple enough to implement without advanced infrastructure.

---

## 2. API Design Principles

### 2.1 Local Web App First

Routes are designed for a local browser UI at:

```text
http://127.0.0.1:8000
```

The app should bind to `127.0.0.1` by default.

Do not design Phase 1 as a hosted multi-user API.

### 2.2 HTML by Default, JSON Only When Useful

Most routes should return:

- Full HTML pages for normal navigation.
- HTML partials for HTMX updates.

JSON responses are allowed for:

- Polling generation status.
- Debug-friendly internal responses.
- Future API-style tests.

Codex should not build a separate REST backend and frontend app.

### 2.3 Simple Route Naming

Use clear route paths based on the workflow:

```text
/projects/{project_id}/story
/projects/{project_id}/characters
/projects/{project_id}/scenes
/projects/{project_id}/prompts
/projects/{project_id}/generation
/projects/{project_id}/outputs
```

Avoid clever route abstractions or generic `/api/resources` patterns.

### 2.4 No Authentication in Phase 1

Phase 1 runs locally for one user.

Do not add:

- Login.
- OAuth.
- Sessions.
- User accounts.
- Role-based access control.

### 2.5 Mandatory Scene Approval

No endpoint may start image generation unless scenes are approved and prompts are valid.

The backend must enforce this rule. The UI hiding a button is not enough.

---

## 3. Response Modes

Each route should support one primary response mode.

| Response mode | Used for | Content-Type |
|---|---|---|
| Full page | Normal browser navigation | `text/html` |
| HTMX partial | Form submit results, cards, progress updates | `text/html` |
| JSON | Status polling, tests, debug-friendly actions | `application/json` |
| Redirect | Successful form flow transition | `303 See Other` |

### 3.1 HTMX Detection

FastAPI route handlers may detect HTMX requests using:

```text
HX-Request: true
```

If `HX-Request` is present, return a partial template.

If not present, return a full page or redirect.

### 3.2 Error Rendering

For HTMX requests, return an error partial.

For normal page requests, render the page with an error banner.

For JSON routes, return the standard error shape in Section 7.

---

## 4. Common Types

## 4.1 Project ID

`project_id` is a local stable identifier.

Recommended format:

```text
lowercase slug + short random suffix
```

Example:

```text
akira-episode-1-a7f3c2
```

Rules:

- Must be URL-safe.
- Must not contain path separators.
- Must map only to a folder under `projects/`.
- Must be validated before path access.

Recommended regex:

```text
^[a-z0-9][a-z0-9-]{2,80}$
```

## 4.2 Scene ID

Scene IDs are stable inside a project.

Format:

```text
scene_001
scene_002
scene_003
```

Scene display order is controlled by `scene_number`.

## 4.3 Prompt ID

Phase 1 can use `scene_id` as the prompt identifier because there is one prompt per approved scene.

## 4.4 Consistency Method

Human-readable name:

```text
IP-Adapter-FaceID
```

Persisted JSON/config/manifest value:

```text
ip-adapter-faceid
```

Do not use underscore-based variants in new APIs, metadata, manifests, or examples.

---

## 5. Common Project State Values

Project state is stored in `metadata/project.json`.

Allowed status values:

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

### 5.1 State Gate Rules

| Action | Required state / files |
|---|---|
| Upload story | Project exists. |
| Upload characters | Project exists. Story should already exist in normal flow. |
| Split scenes | Valid story and character metadata exist. |
| Approve scenes | Valid draft `scenes.json` exists. |
| Generate prompts | Scenes are approved. |
| Start generation | Prompts exist and scenes are approved. |
| View outputs | Project exists. Outputs may be empty. |

Backend services must validate these rules even if the UI already enforces the happy path.

---

## 6. Common Success Shapes

HTML routes should render templates. They do not need a JSON success envelope.

JSON-capable action routes may use this shape in tests or non-HTMX mode:

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "next_url": "/projects/akira-episode-1-a7f3c2/scenes",
  "data": {}
}
```

Rules:

- `ok` must be `true` for successful JSON responses.
- `next_url` should be present when the UI should navigate to another screen.
- `data` should contain route-specific results.

---

## 7. Common Error Shape

JSON error responses must use:

```json
{
  "ok": false,
  "error": {
    "code": "STORY_TOO_LARGE",
    "message": "This story file is too large for Phase 1. Please upload a shorter .md file under 1 MB.",
    "details": {}
  }
}
```

### 7.1 Error Rules

- Do not return raw stack traces to the UI.
- Do not expose OpenAI API keys.
- Do not expose full absolute paths unless debug mode is explicitly enabled.
- Error messages should explain what the user can do next.

### 7.2 HTTP Status Rules

| Situation | HTTP status |
|---|---:|
| Normal success page | `200` |
| Successful form submit redirect | `303` |
| Validation error | `400` |
| Project/file not found | `404` |
| Wrong state transition | `409` |
| Missing OpenAI key or app config | `500` or `503` |
| OpenAI unavailable | `502` or `503` |
| Local model/generation unavailable | `503` |

For HTMX validation errors, returning `200` with an error partial is acceptable when it simplifies UI updates. Service-layer errors must still keep a code.

---

## 8. Route Summary

## 8.1 Page Routes

| Method | Path | Template | Purpose |
|---|---|---|---|
| `GET` | `/` | `home.html` | Home page. |
| `GET` | `/projects/new` | `project_new.html` | Create project form. |
| `GET` | `/projects/{project_id}` | `project_dashboard.html` | Project dashboard. |
| `GET` | `/projects/{project_id}/story` | `story_upload.html` | Story upload page. |
| `GET` | `/projects/{project_id}/characters` | `character_upload.html` | Character upload page. |
| `GET` | `/projects/{project_id}/scenes` | `scene_review.html` | Scene review page. |
| `GET` | `/projects/{project_id}/prompts` | `prompt_review.html` | Prompt review page. |
| `GET` | `/projects/{project_id}/generation` | `generation_progress.html` | Generation page. |
| `GET` | `/projects/{project_id}/outputs` | `output_review.html` | Output review page. |

## 8.2 Action / HTMX Routes

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/projects` | Create project. |
| `POST` | `/projects/{project_id}/story` | Upload story file. |
| `POST` | `/projects/{project_id}/characters` | Upload character images. |
| `DELETE` | `/projects/{project_id}/characters/{character_name}` | Delete character reference if implemented. |
| `POST` | `/projects/{project_id}/scenes/split` | Run GPT scene splitting. |
| `POST` | `/projects/{project_id}/scenes/{scene_id}` | Update one scene. |
| `POST` | `/projects/{project_id}/scenes/reorder` | Reorder scenes. |
| `POST` | `/projects/{project_id}/scenes/{scene_id}/skip` | Skip/delete one scene. |
| `POST` | `/projects/{project_id}/scenes/approve` | Approve final scene list. |
| `POST` | `/projects/{project_id}/prompts/generate` | Generate prompts from approved scenes. |
| `POST` | `/projects/{project_id}/prompts/{scene_id}` | Update prompt for one scene. |
| `POST` | `/projects/{project_id}/prompts/{scene_id}/regenerate` | Regenerate prompt for one scene if implemented. |
| `POST` | `/projects/{project_id}/generation/start` | Start image generation job. |
| `GET` | `/projects/{project_id}/generation/status` | Poll generation status. |
| `POST` | `/projects/{project_id}/generation/cancel` | Cancel current generation job if implemented. |
| `POST` | `/projects/{project_id}/generation/retry-failed` | Retry failed scenes if implemented. |

## 8.3 Utility Routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Local app health check. |
| `GET` | `/projects/{project_id}/outputs/open` | Open output folder if implemented. |

---

## 9. Page Route Details

## 9.1 `GET /`

### Purpose

Render the home page.

### Handler

```text
routes_home.py → home()
```

### Template

```text
templates/home.html
```

### Page data

```json
{
  "app_name": "Local AI Anime Storyboard Generator",
  "recent_projects": []
}
```

Recent projects are optional in Phase 1. If not implemented, show only create/open actions.

---

## 9.2 `GET /projects/new`

### Purpose

Render create project form.

### Handler

```text
routes_projects.py → new_project_page()
```

### Template

```text
templates/project_new.html
```

### Required form fields

| Field | Type | Required | Default |
|---|---|---:|---|
| `project_name` | string | Yes | none |
| `output_preset` | string | Yes | `youtube_standard_720p` |
| `description` | string | No | empty |

### Output preset options

```text
youtube_standard_720p → 1280x720
youtube_high_1080p → 1920x1080
low_vram_preview_540p → 960x540
low_vram_tiny → 768x432
square_preview_1024 → 1024x1024
vertical_short_1080x1920 → 1080x1920
```

---

## 9.3 `GET /projects/{project_id}`

### Purpose

Render project dashboard and current workflow step.

### Handler

```text
routes_projects.py → project_dashboard(project_id)
```

### Template

```text
templates/project_dashboard.html
```

### Page data

```json
{
  "project": {
    "project_id": "akira-episode-1-a7f3c2",
    "project_name": "Akira Episode 1",
    "status": "STORY_UPLOADED",
    "output_preset": "youtube_standard_720p"
  },
  "workflow": {
    "current_step": "characters",
    "next_url": "/projects/akira-episode-1-a7f3c2/characters"
  }
}
```

---

## 9.4 `GET /projects/{project_id}/story`

### Purpose

Render story upload and preview page.

### Handler

```text
routes_story.py → story_page(project_id)
```

### Template

```text
templates/story_upload.html
```

### Page data

- Project metadata.
- Existing story metadata if uploaded.
- Story preview if available.
- Validation errors if any.

---

## 9.5 `GET /projects/{project_id}/characters`

### Purpose

Render character upload and validation page.

### Handler

```text
routes_characters.py → characters_page(project_id)
```

### Template

```text
templates/character_upload.html
```

### Page data

- Existing uploaded characters.
- Character validation status.
- Missing references if scenes have detected characters.
- Extra references warnings.

---

## 9.6 `GET /projects/{project_id}/scenes`

### Purpose

Render scene review page.

### Handler

```text
routes_scenes.py → scenes_page(project_id)
```

### Template

```text
templates/scene_review.html
```

### Page data

- `metadata/scenes.json` if it exists.
- Character warnings.
- Approval state.
- Button to split scenes if no scenes exist.

If no scene list exists, show a CTA:

```text
Analyze Story and Split Scenes
```

---

## 9.7 `GET /projects/{project_id}/prompts`

### Purpose

Render prompt review page.

### Handler

```text
routes_prompts.py → prompts_page(project_id)
```

### Template

```text
templates/prompt_review.html
```

### Page data

- Approved scenes.
- Existing prompts if generated.
- Stale prompt warnings.
- Advanced prompt edit controls if implemented.

---

## 9.8 `GET /projects/{project_id}/generation`

### Purpose

Render generation setup/progress page.

### Handler

```text
routes_generation.py → generation_page(project_id)
```

### Template

```text
templates/generation_progress.html
```

### Page data

- Generation readiness result.
- Current job status if any.
- Hardware profile if detected.
- Low-VRAM warning if relevant.
- Start generation button if ready.

---

## 9.9 `GET /projects/{project_id}/outputs`

### Purpose

Render output review page.

### Handler

```text
routes_outputs.py → outputs_page(project_id)
```

### Template

```text
templates/output_review.html
```

### Page data

- Output image list.
- Manifest summary.
- Failed scenes if any.
- Output folder path.
- Retry failed scenes button if implemented.

---

## 10. Action Route Details

## 10.1 `POST /projects`

### Purpose

Create a new local project.

### Handler

```text
routes_projects.py → create_project()
```

### Service

```text
ProjectService.create_project()
```

### Request content type

```text
application/x-www-form-urlencoded
```

### Form fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `project_name` | string | Yes | 1–120 chars after trim. |
| `description` | string | No | Max 1000 chars. |
| `output_preset` | string | Yes | Must be allowed preset. |

### Success behavior

Create:

```text
projects/{project_id}/
projects/{project_id}/input/
projects/{project_id}/input/characters/
projects/{project_id}/metadata/
projects/{project_id}/metadata/character_cache/
projects/{project_id}/outputs/images/
projects/{project_id}/logs/
projects/{project_id}/metadata/project.json
projects/{project_id}/metadata/generation_settings.json
```

Then redirect:

```text
303 → /projects/{project_id}/story
```

### JSON success example

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "next_url": "/projects/akira-episode-1-a7f3c2/story",
  "data": {
    "status": "CREATED"
  }
}
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `PROJECT_NAME_REQUIRED` | 400 | Missing project name. |
| `PROJECT_NAME_INVALID` | 400 | Name cannot produce safe project ID. |
| `OUTPUT_PRESET_INVALID` | 400 | Unsupported preset. |
| `PROJECT_CREATE_FAILED` | 500 | Folder or metadata write failed. |

---

## 10.2 `POST /projects/{project_id}/story`

### Purpose

Upload and validate a free-form Markdown story.

### Handler

```text
routes_story.py → upload_story(project_id)
```

### Service

```text
StoryService.validate_story_upload()
StoryService.save_story()
```

### Request content type

```text
multipart/form-data
```

### Form fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `story_file` | file | Yes | `.md`, UTF-8, non-empty, under limit. |

### Stored files

```text
input/story.md
metadata/story.json
```

### Success behavior

If normal request:

```text
303 → /projects/{project_id}/characters
```

If HTMX request, return:

```text
templates/partials/_story_validation.html
```

### JSON success example

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "next_url": "/projects/akira-episode-1-a7f3c2/characters",
  "data": {
    "story_status": "UPLOADED",
    "original_filename": "episode_1.md",
    "stored_path": "input/story.md",
    "story_char_count": 38120,
    "approx_word_count": 7100,
    "content_hash": "sha256:..."
  }
}
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `PROJECT_NOT_FOUND` | 404 | Project folder does not exist. |
| `STORY_FILE_REQUIRED` | 400 | No story file uploaded. |
| `STORY_UNSUPPORTED_FILE_TYPE` | 400 | File extension is not `.md`. |
| `STORY_INVALID_ENCODING` | 400 | File cannot be decoded as UTF-8. |
| `STORY_EMPTY` | 400 | No meaningful text. |
| `STORY_TOO_LARGE` | 400 | File exceeds Phase 1 limit. |
| `STORY_BINARY_CONTENT_DETECTED` | 400 | File looks binary. |
| `STORY_SAVE_FAILED` | 500 | Could not save story locally. |

---

## 10.3 `POST /projects/{project_id}/characters`

### Purpose

Upload one or more character reference images.

### Handler

```text
routes_characters.py → upload_characters(project_id)
```

### Service

```text
CharacterService.validate_image()
CharacterService.save_character_references()
```

### Request content type

```text
multipart/form-data
```

### Form fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `character_files` | file[] | Yes | `.png`, `.jpg`, `.jpeg`, `.webp`; decodable image. |

### Stored files

```text
input/characters/{CharacterName}.{ext}
metadata/characters.json
```

### Success behavior

If normal request:

```text
303 → /projects/{project_id}/scenes
```

If HTMX request, return:

```text
templates/partials/_character_validation.html
```

### JSON success example

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "next_url": "/projects/akira-episode-1-a7f3c2/scenes",
  "data": {
    "characters": [
      {
        "name": "Akira",
        "stored_path": "input/characters/Akira.png",
        "width": 1024,
        "height": 1536,
        "status": "valid",
        "warnings": [],
        "consistency_method": "ip-adapter-faceid"
      }
    ]
  }
}
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `PROJECT_NOT_FOUND` | 404 | Project does not exist. |
| `CHARACTER_FILE_REQUIRED` | 400 | No image uploaded. |
| `UNSUPPORTED_CHARACTER_IMAGE_TYPE` | 400 | Unsupported extension. |
| `CORRUPT_CHARACTER_IMAGE` | 400 | Image cannot be decoded. |
| `DUPLICATE_CHARACTER_NAME` | 400 | Two files map to same character name. |
| `INVALID_CHARACTER_FILENAME` | 400 | Filename cannot produce a safe character name. |
| `CHARACTER_IMAGE_TOO_LARGE` | 400 | Image exceeds configured limit. |
| `CHARACTER_SAVE_FAILED` | 500 | Could not save image or metadata. |

---

## 10.4 `DELETE /projects/{project_id}/characters/{character_name}`

### Purpose

Delete a character reference.

This is optional in first implementation. If omitted, users can replace project files by re-uploading or creating a new project.

### Handler

```text
routes_characters.py → delete_character(project_id, character_name)
```

### Success behavior

Return updated character validation partial:

```text
templates/partials/_character_validation.html
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `PROJECT_NOT_FOUND` | 404 | Project does not exist. |
| `CHARACTER_NOT_FOUND` | 404 | Character reference does not exist. |
| `CHARACTER_DELETE_FAILED` | 500 | Could not delete file or update metadata. |

---

## 10.5 `POST /projects/{project_id}/scenes/split`

### Purpose

Run GPT scene splitting from the uploaded story and character metadata.

### Handler

```text
routes_scenes.py → split_scenes(project_id)
```

### Service

```text
OpenAISceneService.split_story_into_scenes()
```

### Request content type

```text
application/x-www-form-urlencoded
```

No required form fields for MVP.

Optional future fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `scene_count_hint` | int | No | Rough user hint only. |

### Precondition

- `metadata/story.json` exists and is valid.
- `input/story.md` exists.
- `metadata/characters.json` exists or the user has accepted proceeding without complete character mapping.
- OpenAI API key exists.

### Stored files

```text
metadata/scenes.json
```

### Success behavior

If normal request:

```text
303 → /projects/{project_id}/scenes
```

If HTMX request, return scene cards partial or full review area:

```text
templates/partials/_scene_list.html
```

### JSON success example

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "next_url": "/projects/akira-episode-1-a7f3c2/scenes",
  "data": {
    "scene_count": 3,
    "status": "SCENES_GENERATED"
  }
}
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `PROJECT_NOT_FOUND` | 404 | Project does not exist. |
| `STORY_NOT_UPLOADED` | 409 | Story is missing. |
| `OPENAI_API_KEY_MISSING` | 503 | API key not configured. |
| `SCENE_SPLIT_FAILED` | 502 | OpenAI request failed. |
| `SCENE_JSON_INVALID` | 502 | Response was not valid JSON. |
| `SCENE_SCHEMA_INVALID` | 502 | Response did not match schema. |
| `STORY_TOO_LARGE_FOR_MODEL` | 400 | Story does not fit configured model and chunking is not implemented. |
| `METADATA_WRITE_FAILED` | 500 | Could not save scenes. |

---

## 10.6 `POST /projects/{project_id}/scenes/{scene_id}`

### Purpose

Update one scene from the review UI.

### Handler

```text
routes_scenes.py → update_scene(project_id, scene_id)
```

### Request content type

```text
application/x-www-form-urlencoded
```

### Form fields

| Field | Type | Required | Notes |
|---|---|---:|---|
| `title` | string | Yes | Max recommended 80 chars. |
| `summary` | string | Yes | Must not be empty. |
| `source_excerpt` | string | Yes | Can be edited for review clarity. |
| `characters` | string | No | Comma-separated names for HTMX form simplicity. |
| `location` | string | No | Short text. |
| `time_of_day` | string | No | Short text. |
| `mood` | string | No | Short text. |
| `main_action` | string | No | Short text. |
| `camera_shot` | string | No | Short text. |
| `camera_angle` | string | No | Short text. |
| `visual_details` | string | No | Newline-separated details. |
| `continuity_notes` | string | No | Newline-separated notes. |

### Success behavior

Return updated scene card partial:

```text
templates/partials/_scene_card.html
```

Prompts for the scene must be marked stale if they already exist.

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `SCENE_NOT_FOUND` | 404 | Scene ID not found. |
| `SCENE_UPDATE_INVALID` | 400 | Required fields missing or invalid. |
| `SCENE_ALREADY_GENERATED` | 409 | Optional: block edits after generation unless regeneration flow is supported. |
| `METADATA_WRITE_FAILED` | 500 | Could not save scene update. |

---

## 10.7 `POST /projects/{project_id}/scenes/reorder`

### Purpose

Update scene order.

### Handler

```text
routes_scenes.py → reorder_scenes(project_id)
```

### Request content type

```text
application/json
```

Using JSON is simpler for drag-and-drop reorder.

### Request body

```json
{
  "scene_ids": ["scene_002", "scene_001", "scene_003"]
}
```

### Success behavior

- Reassign `scene_number` sequentially from 1.
- Mark prompts stale if prompts already exist.
- Return updated scene list partial.

```text
templates/partials/_scene_list.html
```

### JSON success example

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "data": {
    "scene_count": 3,
    "scene_ids": ["scene_002", "scene_001", "scene_003"]
  }
}
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `SCENE_REORDER_INVALID` | 400 | Missing, duplicate, or unknown scene IDs. |
| `SCENE_LIST_NOT_FOUND` | 404 | No scenes exist. |
| `METADATA_WRITE_FAILED` | 500 | Could not save reordered scenes. |

---

## 10.8 `POST /projects/{project_id}/scenes/{scene_id}/skip`

### Purpose

Mark one scene as skipped or remove it from the active generation list.

Recommended MVP behavior:

```text
Set status = skipped and renumber active scenes for generation/output.
```

### Handler

```text
routes_scenes.py → skip_scene(project_id, scene_id)
```

### Success behavior

Return updated scene list partial.

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `SCENE_NOT_FOUND` | 404 | Scene ID not found. |
| `SCENE_SKIP_INVALID` | 400 | Cannot skip the last remaining active scene. |
| `METADATA_WRITE_FAILED` | 500 | Could not save scene update. |

---

## 10.9 `POST /projects/{project_id}/scenes/approve`

### Purpose

Approve final scene list before prompt generation.

### Handler

```text
routes_scenes.py → approve_scenes(project_id)
```

### Service

```text
SceneService.approve_scenes()
```

If no separate `SceneService` exists, this can live in `OpenAISceneService` or a simple scene metadata service. Keep route logic thin.

### Precondition

- Scene list exists.
- At least one non-skipped scene exists.
- Required scene fields are valid.
- Character reference warnings have been surfaced.

### Success behavior

- Set active scenes to `approved`.
- Set project status to `SCENES_APPROVED`.
- Redirect:

```text
303 → /projects/{project_id}/prompts
```

### JSON success example

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "next_url": "/projects/akira-episode-1-a7f3c2/prompts",
  "data": {
    "approved_scene_count": 3,
    "status": "SCENES_APPROVED"
  }
}
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `SCENE_LIST_NOT_FOUND` | 404 | No scene list exists. |
| `SCENE_APPROVAL_INVALID` | 400 | Scene list has invalid or empty required fields. |
| `SCENE_APPROVAL_REQUIRED` | 409 | Used when another action tries to proceed without approval. |
| `CHARACTER_REFERENCE_MISSING` | 409 | Required main character reference missing. |
| `METADATA_WRITE_FAILED` | 500 | Could not save approval state. |

---

## 10.10 `POST /projects/{project_id}/prompts/generate`

### Purpose

Generate image prompts for approved scenes.

### Handler

```text
routes_prompts.py → generate_prompts(project_id)
```

### Service

```text
OpenAIPromptService.generate_prompts()
```

### Precondition

- Scenes are approved.
- OpenAI API key exists.
- Character metadata is valid enough for prompt generation.

### Stored files

```text
metadata/prompts.json
```

### Success behavior

If normal request:

```text
303 → /projects/{project_id}/prompts
```

If HTMX request:

```text
templates/partials/_prompt_list.html
```

### JSON success example

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "next_url": "/projects/akira-episode-1-a7f3c2/prompts",
  "data": {
    "prompt_count": 3,
    "status": "PROMPTS_GENERATED"
  }
}
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `SCENE_APPROVAL_REQUIRED` | 409 | Scenes are not approved. |
| `OPENAI_API_KEY_MISSING` | 503 | API key not configured. |
| `PROMPT_GENERATION_FAILED` | 502 | OpenAI request failed. |
| `PROMPT_JSON_INVALID` | 502 | Response was not valid JSON. |
| `PROMPT_SCHEMA_INVALID` | 502 | Prompt JSON failed validation. |
| `METADATA_WRITE_FAILED` | 500 | Could not save prompts. |

---

## 10.11 `POST /projects/{project_id}/prompts/{scene_id}`

### Purpose

Update one prompt manually.

### Handler

```text
routes_prompts.py → update_prompt(project_id, scene_id)
```

### Request content type

```text
application/x-www-form-urlencoded
```

### Form fields

| Field | Type | Required | Notes |
|---|---|---:|---|
| `positive_prompt` | string | Yes | Must not be empty. |
| `negative_prompt` | string | Yes | Must not be empty. |

### Success behavior

- Update prompt.
- Set `manual_edit = true`.
- Set prompt `status = ready` if valid.
- Return prompt card partial.

```text
templates/partials/_prompt_card.html
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `PROMPT_NOT_FOUND` | 404 | Prompt for scene not found. |
| `PROMPT_UPDATE_INVALID` | 400 | Prompt text missing or invalid. |
| `METADATA_WRITE_FAILED` | 500 | Could not save prompt. |

---

## 10.12 `POST /projects/{project_id}/prompts/{scene_id}/regenerate`

### Purpose

Regenerate one prompt from the approved scene.

This is optional for first implementation. Full prompt regeneration for all scenes is enough for MVP.

### Handler

```text
routes_prompts.py → regenerate_prompt(project_id, scene_id)
```

### Special rule

If the prompt has `manual_edit = true`, require an explicit form field:

```text
confirm_overwrite=true
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `PROMPT_MANUAL_EDIT_OVERWRITE_REQUIRED` | 409 | User must confirm overwrite. |
| `PROMPT_GENERATION_FAILED` | 502 | OpenAI request failed. |
| `PROMPT_SCHEMA_INVALID` | 502 | Regenerated prompt invalid. |

---

## 10.13 `POST /projects/{project_id}/generation/start`

### Purpose

Start local image generation.

### Handler

```text
routes_generation.py → start_generation(project_id)
```

### Service

```text
GenerationJobService.start_job()
GenerationService.generate_project_images()
```

### Precondition

- `metadata/scenes.json` exists.
- Scenes are approved.
- `metadata/prompts.json` exists.
- Prompts are valid and ready.
- Required character references exist.
- Output folder is writable.
- No other generation job is currently running.

### Request content type

```text
application/x-www-form-urlencoded
```

### Optional form fields

| Field | Type | Required | Notes |
|---|---|---:|---|
| `generation_mode` | string | No | `auto`, `low_vram`, `cpu`, `quality`; default `auto`. |
| `confirm_cpu_slow` | boolean | No | Required if CPU-only mode needs explicit acknowledgement. |
| `confirm_low_vram_faceid_disabled` | boolean | No | Required if UI wants explicit low-VRAM acknowledgement. |

### Success behavior

- Create/update `metadata/generation_status.json`.
- Set project status to `GENERATION_RUNNING`.
- Start one background generation job.
- Redirect:

```text
303 → /projects/{project_id}/generation
```

For HTMX:

```text
templates/partials/_generation_status.html
```

### JSON success example

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "next_url": "/projects/akira-episode-1-a7f3c2/generation",
  "data": {
    "job_id": "gen_20260611_101530",
    "status": "running",
    "total_scenes": 3
  }
}
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `GENERATION_NOT_READY` | 409 | Readiness check failed. |
| `SCENE_APPROVAL_REQUIRED` | 409 | Scenes are not approved. |
| `PROMPTS_MISSING` | 409 | Prompts are missing. |
| `PROMPT_STALE` | 409 | One or more prompts are stale. |
| `CHARACTER_REFERENCE_MISSING` | 409 | Required character reference missing. |
| `GENERATION_ALREADY_RUNNING` | 409 | Another job is running. |
| `OUTPUT_FOLDER_NOT_WRITABLE` | 500 | Cannot write outputs. |
| `MODEL_CONFIG_INVALID` | 500 | Required model ID/config invalid. |

---

## 10.14 `GET /projects/{project_id}/generation/status`

### Purpose

Poll generation job status.

### Handler

```text
routes_generation.py → generation_status(project_id)
```

### Response mode

If HTMX:

```text
templates/partials/_generation_status.html
```

If JSON requested:

```json
{
  "ok": true,
  "project_id": "akira-episode-1-a7f3c2",
  "data": {
    "job_id": "gen_20260611_101530",
    "status": "running",
    "current_scene_number": 2,
    "current_scene_title": "Hana hears the warning",
    "total_scenes": 3,
    "completed_scenes": 1,
    "failed_scenes": 0,
    "progress_percent": 33,
    "current_message": "Generating scene 2 of 3",
    "outputs": [
      {
        "scene_id": "scene_001",
        "scene_number": 1,
        "status": "success",
        "output_path": "outputs/images/001_akira_enters_school.png"
      }
    ],
    "errors": []
  }
}
```

### Job status values

```text
queued
running
completed
partial
failed
cancel_requested
cancelled
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `GENERATION_STATUS_NOT_FOUND` | 404 | No generation status exists. |
| `PROJECT_NOT_FOUND` | 404 | Project does not exist. |

---

## 10.15 `POST /projects/{project_id}/generation/cancel`

### Purpose

Request cancellation of the current generation job.

This is optional for the first MVP. If cancellation is not implemented, hide the button and return `GENERATION_CANCEL_NOT_SUPPORTED` if called.

### Handler

```text
routes_generation.py → cancel_generation(project_id)
```

### Success behavior

Set job status to:

```text
cancel_requested
```

The generation thread should stop safely after the current scene if possible.

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `GENERATION_CANCEL_NOT_SUPPORTED` | 501 | Cancellation not implemented. |
| `GENERATION_JOB_NOT_RUNNING` | 409 | No running job to cancel. |

---

## 10.16 `POST /projects/{project_id}/generation/retry-failed`

### Purpose

Retry scenes that failed in the last generation run.

This is recommended but can be implemented after the first generation path works.

### Handler

```text
routes_generation.py → retry_failed(project_id)
```

### Precondition

- Previous generation status is `partial` or `failed`.
- Failed scenes are known in `generation_status.json` or `manifest.json`.
- Prompts are still valid.
- No generation job is running.

### Success behavior

Start a new job for failed scenes only.

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `NO_FAILED_SCENES_TO_RETRY` | 409 | Nothing to retry. |
| `PROMPT_STALE` | 409 | Prompt changed or is stale. |
| `GENERATION_ALREADY_RUNNING` | 409 | Another job is running. |

---

## 10.17 `GET /projects/{project_id}/outputs/open`

### Purpose

Open the local output folder in Windows Explorer.

This is optional. If implemented, keep it local-only and safe.

### Handler

```text
routes_outputs.py → open_outputs_folder(project_id)
```

### Windows behavior

Use a safe subprocess call equivalent to:

```text
explorer.exe projects\{project_id}\outputs\images
```

Do not pass unsanitized user input to a shell string.

### Success behavior

Return an HTMX flash partial:

```text
Output folder opened.
```

### Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `OUTPUT_FOLDER_NOT_FOUND` | 404 | Output folder does not exist. |
| `OPEN_OUTPUT_FOLDER_FAILED` | 500 | OS command failed. |

---

## 10.18 `GET /health`

### Purpose

Local app health check.

### Handler

```text
routes_home.py → health()
```

### JSON response

```json
{
  "ok": true,
  "status": "healthy",
  "app": "local-ai-anime-storyboard-generator"
}
```

Do not run heavy checks such as loading SDXL in this endpoint.

---

## 11. Metadata Schemas Referenced by Routes

Full schemas belong in `docs/10-data-storage-spec.md`. This section defines route-facing minimum shapes.

## 11.1 Project Metadata Minimum

```json
{
  "version": 1,
  "project_id": "akira-episode-1-a7f3c2",
  "project_name": "Akira Episode 1",
  "description": "",
  "status": "CREATED",
  "output_preset": {
    "id": "youtube_standard_720p",
    "name": "YouTube Standard",
    "width": 1280,
    "height": 720,
    "aspect_ratio": "16:9"
  },
  "created_at": "2026-06-11T10:00:00Z",
  "updated_at": "2026-06-11T10:00:00Z"
}
```

## 11.2 Character Route Minimum

```json
{
  "name": "Akira",
  "original_filename": "Akira.png",
  "stored_path": "input/characters/Akira.png",
  "mime_type": "image/png",
  "width": 1024,
  "height": 1536,
  "file_size_bytes": 842120,
  "status": "valid",
  "warnings": [],
  "consistency_method": "ip-adapter-faceid"
}
```

## 11.3 Scene Route Minimum

```json
{
  "scene_id": "scene_001",
  "scene_number": 1,
  "title": "Akira enters the school",
  "source_excerpt": "Akira stepped through the rusted gate...",
  "summary": "Akira enters an abandoned school at dusk and senses something is wrong.",
  "characters": ["Akira"],
  "location": "abandoned school gate",
  "time_of_day": "dusk",
  "mood": "tense, mysterious",
  "main_action": "Akira walks through the school gate",
  "camera_shot": "wide shot",
  "camera_angle": "slightly low angle",
  "visual_details": ["rusted gate", "orange sunset light", "empty school courtyard"],
  "continuity_notes": ["Akira wears the same outfit as the uploaded reference image"],
  "status": "draft"
}
```

## 11.4 Prompt Route Minimum

```json
{
  "scene_id": "scene_001",
  "scene_number": 1,
  "positive_prompt": "anime storyboard illustration, cinematic wide shot, Akira entering an abandoned school gate at dusk, tense atmosphere",
  "negative_prompt": "low quality, blurry, distorted face, bad hands, text, watermark, logo",
  "characters": [
    {
      "name": "Akira",
      "reference_image_path": "input/characters/Akira.png",
      "consistency_method": "ip-adapter-faceid",
      "role_in_scene": "main character",
      "visual_priority": "high"
    }
  ],
  "generation_settings": {
    "width": 1280,
    "height": 720,
    "num_images": 1,
    "seed": null,
    "guidance_scale": 7.0,
    "num_inference_steps": 30
  },
  "status": "ready",
  "manual_edit": false
}
```

---

## 12. Validation Rules by Workflow

## 12.1 Create Project Validation

- `project_name` must not be empty.
- `output_preset` must be known.
- Generated `project_id` must be safe.
- Project folder must not collide with an existing folder unless conflict resolution appends a suffix.

## 12.2 Story Upload Validation

- Uploaded file is required.
- Extension must be `.md`.
- File must decode as UTF-8.
- File must not be empty after trimming.
- File must not exceed Phase 1 size limits.
- File path must be controlled by app, not upload filename.

## 12.3 Character Upload Validation

- At least one file is required.
- Extension must be `.png`, `.jpg`, `.jpeg`, or `.webp`.
- Image must decode with Pillow.
- Character name is derived from filename stem.
- Duplicate character names are rejected.
- Stored path must stay inside `input/characters/`.

## 12.4 Scene Approval Validation

- Scene list exists.
- At least one active scene exists.
- Scene numbers are sequential.
- Every active scene has a title and summary.
- Every active scene has a valid status.
- Missing required character references are blocked or explicitly handled based on character spec.

## 12.5 Prompt Generation Validation

- Scenes are approved.
- Approved scene count matches prompt count.
- Prompts include positive and negative prompt text.
- Prompt dimensions match selected output preset.
- Character references use `ip-adapter-faceid` where applicable.

## 12.6 Generation Start Validation

- Scenes are approved.
- Prompts exist and are valid.
- No prompt is stale.
- Output directory is writable.
- No job is already running.
- Hardware mode is resolved.
- Low-VRAM fallback is applied when needed.

---

## 13. HTMX Partial Templates

Recommended partials:

| Partial | Used by |
|---|---|
| `partials/_flash.html` | Generic success/error messages. |
| `partials/_story_validation.html` | Story upload result. |
| `partials/_character_validation.html` | Character upload/delete result. |
| `partials/_scene_list.html` | Scene splitting, reorder, skip. |
| `partials/_scene_card.html` | Single scene update. |
| `partials/_prompt_list.html` | Prompt generation. |
| `partials/_prompt_card.html` | Single prompt update. |
| `partials/_generation_status.html` | Generation status polling. |
| `partials/_output_grid.html` | Output review updates. |

### 13.1 Generation Polling Example

In `generation_progress.html`:

```html
<div
  id="generation-status"
  hx-get="/projects/{{ project.project_id }}/generation/status"
  hx-trigger="load, every 2s"
  hx-swap="outerHTML">
  {% include "partials/_generation_status.html" %}
</div>
```

Stop polling in the partial when status is one of:

```text
completed
partial
failed
cancelled
```

---

## 14. File Upload Security Rules

All upload endpoints must:

1. Ignore directory parts from uploaded filename.
2. Validate extension.
3. Validate content.
4. Store using app-controlled destination path.
5. Prevent `../` path traversal.
6. Use project-relative paths in metadata.
7. Never execute uploaded content.

Markdown preview must be sanitized with `nh3` if rendered as HTML.

Do not use deprecated `bleach` in new code.

---

## 15. OpenAI Route Rules

Scene splitting and prompt generation routes must:

- Use configured model IDs from settings.
- Use JSON/structured output mode supported by the installed OpenAI SDK.
- Validate returned JSON with Pydantic before saving.
- Log model identifier and request metadata.
- Never log the OpenAI API key.
- Never silently truncate story text.
- Return friendly retryable errors when OpenAI fails.

Recommended settings:

```text
OPENAI_SCENE_MODEL=gpt-5.4-mini
OPENAI_PROMPT_MODEL=gpt-5.4-mini
```

---

## 16. Generation Route Rules

Generation routes must:

- Start only one local generation job at a time.
- Run scene-by-scene.
- Save progress to `metadata/generation_status.json`.
- Save outputs under `outputs/images/`.
- Update `outputs/manifest.json` after each scene or at safe checkpoints.
- Continue remaining scenes after a per-scene failure when safe.
- Stop on global failures such as model load failure or first-scene CUDA out-of-memory.

On 4GB VRAM / low-VRAM mode:

- Disable IP-Adapter-FaceID by default.
- Use SD 1.5 fallback or low-resolution preset.
- Use prompt-based character hints.
- Explain the fallback in simple UI language.

---

## 17. Output Filename Rules

Generation output filenames must preserve approved scene order.

Recommended format:

```text
{scene_number_padded}_{scene_slug}.png
```

Example:

```text
001_akira_enters_school.png
002_hana_warning.png
003_dark_hallway.png
```

Rules:

- Use 3-digit numeric prefix for Phase 1.
- Slug must be filesystem-safe.
- Do not rely on user-provided title without sanitization.
- If filename exists, either overwrite only on explicit regeneration or append a run suffix.

The final generation pipeline doc may refine overwrite/run behavior.

---

## 18. Minimal FastAPI Router Layout

Recommended route files:

```text
app/web/routes_home.py
app/web/routes_projects.py
app/web/routes_story.py
app/web/routes_characters.py
app/web/routes_scenes.py
app/web/routes_prompts.py
app/web/routes_generation.py
app/web/routes_outputs.py
```

Router prefixes may stay simple.

Example:

```python
router = APIRouter()

@router.get("/projects/{project_id}/story")
def story_page(project_id: str):
    ...

@router.post("/projects/{project_id}/story")
def upload_story(project_id: str, story_file: UploadFile):
    ...
```

Do not put all routes in `main.py`.

---

## 19. Endpoint Implementation Priority

Codex Agent should implement endpoints in this order:

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
14. POST /projects/{project_id}/scenes/approve
15. GET /projects/{project_id}/prompts
16. POST /projects/{project_id}/prompts/generate with mocked OpenAI first
17. POST /projects/{project_id}/prompts/{scene_id}
18. GET /projects/{project_id}/generation
19. POST /projects/{project_id}/generation/start with mocked generation first
20. GET /projects/{project_id}/generation/status
21. GET /projects/{project_id}/outputs
22. Optional retry/cancel/open-folder routes
```

Build mock OpenAI and mock generation before wiring real AI.

---

## 20. Out of Scope

Do not add these routes in Phase 1:

- User registration or login routes.
- Admin routes.
- Cloud project sync routes.
- Payment routes.
- Public sharing routes.
- Video generation routes.
- Audio generation routes.
- Subtitle routes.
- Timeline export routes.
- WebSocket API unless explicitly approved later.
- GraphQL API.
- Separate `/api/v1` public REST API layer.

---

## 21. API Guardrails

Codex Agent must follow these rules:

1. Do not start generation before scene approval.
2. Do not skip prompt validation.
3. Do not trust uploaded filenames as paths.
4. Do not store absolute paths in normal metadata.
5. Do not store OpenAI API keys in project files.
6. Do not expose stack traces in the UI.
7. Do not add authentication or multi-user concepts.
8. Do not add a database.
9. Do not add React or frontend build tooling.
10. Do not add queues or microservices.
11. Do not add video-generation endpoints.
12. Persist character consistency method as `ip-adapter-faceid`.
13. Use `nh3` for HTML sanitization if Markdown is rendered as HTML.
14. Keep all route behavior local-first and implementation-friendly.

---

## 22. Final API Definition

Phase 1 API is a simple local HTTP interface for a server-rendered creator workflow:

```text
Create project
→ upload story
→ upload characters
→ split scenes
→ review/edit/reorder scenes
→ approve scenes
→ generate prompts
→ review/edit prompts
→ start local image generation
→ poll progress
→ review ordered outputs
```

The API should be boring, explicit, and easy for Codex Agent to implement. Do not introduce advanced API patterns unless a later product decision requires them.
