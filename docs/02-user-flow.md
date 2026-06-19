# Local AI Anime Storyboard Generator — User Flow

**Document:** `docs/02-user-flow.md`  
**Product name:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Status:** Draft based on confirmed product decisions  
**Primary user:** Non-technical anime/story creator  

---

## 1. Purpose

This document defines the end-to-end user flow for Phase 1 of the Local AI Anime Storyboard Generator.

The goal is to make the app feel simple for a non-technical creator while still giving enough control to prevent bad generation results.

The expected experience is:

```text
Upload story → upload character images → app splits scenes → user reviews scenes → click generate → get ordered image assets
```

Phase 1 is image-only. The app must not include video generation, voice generation, lip-sync, subtitle generation, or timeline export in this flow.

---

## 2. User Flow Principles

### 2.1 Non-Technical First

The user should never be forced to understand:

- Prompt engineering.
- Diffusion pipeline internals.
- ComfyUI graphs.
- IP-Adapter configuration.
- GPU tuning.
- Model checkpoint details.
- Seed behavior.

Advanced settings may exist later, but the default flow must stay simple.

### 2.2 Local-First

All project files, uploaded inputs, generated metadata, generated images, and logs are saved on the user's local machine.

The app may use the OpenAI API for story understanding and scene splitting, but image generation runs locally.

### 2.3 Mandatory Scene Review

The system must not start image generation immediately after GPT scene splitting.

The user must review and approve the generated scene list before image generation starts.

This is a hard Phase 1 product rule because free-form story parsing can be imperfect.

### 2.4 Ordered Output

Every output image must preserve story order through numeric filename prefixes.

Example:

```text
001_akira_enters_school.png
002_hana_warning.png
003_dark_hallway.png
```

---

## 3. Actors

### 3.1 Primary Actor

**Creator**

A non-technical user who wants to turn a Markdown story and character references into ordered anime storyboard images.

### 3.2 System Components Involved

- Local web UI built with Jinja2 + HTMX.
- FastAPI backend.
- OpenAI scene splitting / prompting service.
- Local Diffusers image generation service.
- IP-Adapter-FaceID character consistency component.
- Local project storage.

---

## 4. High-Level Flow

```text
1. Open app
2. Create project
3. Upload story.md
4. Upload character reference images
5. Validate inputs
6. Split story into scenes using GPT
7. Review and edit scene list
8. Approve scene list
9. Generate prompts
10. Generate images locally
11. Save ordered output files
12. Review output folder
```

---

## 5. Entry Flow

### 5.1 Open Local App

The user starts the local app on Windows.

Expected startup behavior:

1. User runs a startup script or executable.
2. Backend starts locally.
3. Browser opens local web UI.

Expected local URL:

```text
http://localhost:8000
```

### 5.2 Landing Page

The landing page should show:

- Product name.
- Simple description.
- Button to create a new project.
- Optional button to open an existing project.
- Basic local generation status if available.

Suggested text:

```text
Create anime storyboard images from your story and character references.
```

Primary action:

```text
Create New Project
```

Secondary action:

```text
Open Existing Project
```

---

## 6. Project Creation Flow

### 6.1 Create Project Screen

The user enters basic project information.

Required fields:

| Field | Required | Notes |
|---|---:|---|
| Project name | Yes | Human-readable name. |
| Output preset | Yes | Default: YouTube Standard — 1280x720, 16:9. |

Optional fields:

| Field | Required | Notes |
|---|---:|---|
| Description | No | Local project note only. |

### 6.2 Output Preset Selection

Default selected preset:

```text
YouTube Standard — 1280x720, 16:9
```

Other presets may be available:

```text
YouTube High — 1920x1080, 16:9
Low VRAM Preview — 960x540, 16:9
Square Preview — 1024x1024, 1:1
Vertical Short — 1080x1920, 9:16
```

For Phase 1, the default should prioritize YouTube-style desktop viewing without looking broken, tiny, or heavily pixelated.

### 6.3 Project Folder Creation

After project creation, the system creates a local folder.

Recommended structure:

```text
projects/
  {project_id}/
    input/
      story.md
      characters/
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
      manifest.json
    logs/
      app.log
      generation.log
```

---

## 7. Story Upload Flow

### 7.1 Upload Story Screen

The user uploads a free-form Markdown story file.

Allowed input:

```text
.md
```

The user is not required to write structured scene tags.

The story can contain:

- Narration.
- Dialogue.
- Character names.
- Scene descriptions.
- Emotional beats.
- Action beats.

### 7.2 Story Validation

The system validates:

| Validation | Behavior |
|---|---|
| File exists | Block continue if missing. |
| File extension is `.md` | Block unsupported files. |
| File can be read as text | Show readable error if parsing fails. |
| File is not empty | Block empty story. |

### 7.3 Story Preview

After upload, the user sees a preview of the story text.

The screen should include:

- Filename.
- Text preview.
- Basic word/character count.
- Continue button.

Primary action:

```text
Continue to Character Upload
```

---

## 8. Character Reference Upload Flow

### 8.1 Upload Character Images Screen

The user uploads one full-body character image for each main character.

Supported image types should include:

```text
.png
.jpg
.jpeg
.webp
```

Each image should include:

- Face.
- Body.
- Outfit.
- Overall anime style.

### 8.2 Filename Matching Rule

Character image filenames must match character names used in the story.

Example:

```text
Akira.png
Hana.png
Yuki.png
```

If the story uses the character name `Akira`, the app should look for an uploaded character file named `Akira`.

The comparison should ignore file extension.

### 8.3 Detected Character List

The system may use GPT to detect likely character names from the uploaded story.

The UI should show:

| Character | Matching image | Status |
|---|---|---|
| Akira | Akira.png | Ready |
| Hana | Hana.png | Ready |
| Yuki | Missing | Needs image |

### 8.4 Character Validation

The system validates:

| Validation | Behavior |
|---|---|
| At least one character image uploaded | Block continue if missing. |
| Filename can map to a character name | Warn or block depending on severity. |
| File can be opened as image | Block invalid image. |
| Duplicate character filenames | Block duplicate names. |
| Missing image for detected main character | Ask user to upload image or mark character as not required. |

### 8.5 User Override

Because automatic character detection can be imperfect, the user should be able to:

- Rename a detected character.
- Mark a detected character as not a main character.
- Add a missing character manually.
- Replace an uploaded image.
- Continue with warnings only when the missing character will not be used for generation.

### 8.6 Character Consistency Method

Phase 1 should use **IP-Adapter-FaceID** for character identity guidance when generating images when the user's hardware can support it.

Low-VRAM fallback rule:

- The Phase 1 minimum target is still 4GB VRAM, but 4GB VRAM should be treated as low-VRAM mode.
- SDXL plus IP-Adapter-FaceID may exceed 4GB VRAM and cause out-of-memory errors.
- On 4GB VRAM machines, IP-Adapter-FaceID must be disabled by default.
- In that fallback mode, the app should use SD 1.5 or a low-resolution preset plus prompt-based character hints such as character name, outfit reminder, and visual identity notes.
- The UI should explain this in plain language, not by exposing adapter internals in the default flow.

Product expectation:

```text
The app should try to preserve each character's face, outfit, and visual identity based on the uploaded full-body reference image.
```

The app must not promise perfect identity preservation.

Avoid this wording:

```text
The character's face will never change.
```

Reason:

- One reference image is not enough to guarantee perfect identity lock.
- IP-Adapter-FaceID can guide identity, but results can still drift depending on pose, lighting, angle, composition, prompt conflict, and model behavior.
- Outfit consistency still requires prompt support because FaceID guidance focuses more on identity than full clothing preservation.

### 8.7 Continue Action

Primary action:

```text
Analyze Story and Split Scenes
```

When clicked, the system starts GPT-based scene splitting.

---

## 9. Scene Splitting Flow

### 9.1 GPT Scene Splitting

The system sends story content and character metadata to GPT.

GPT should produce an ordered scene list.

Each scene should include:

| Field | Required | Description |
|---|---:|---|
| Scene number | Yes | Starts at 1 and follows story order. |
| Scene title | Yes | Short human-readable title. |
| Source text range or excerpt | Yes | Helps user verify scene mapping. |
| Scene summary | Yes | Short summary of what happens. |
| Characters present | Yes | Names of characters in the scene. |
| Location | Recommended | Main setting if detectable. |
| Mood | Recommended | Emotional tone. |
| Key action | Recommended | Main visible action. |
| Draft visual prompt | Recommended | Initial prompt for image generation. |

### 9.2 Loading State

The UI should show a clear loading state while GPT is processing.

Suggested message:

```text
Analyzing your story and preparing scenes...
```

The user should not need to understand GPT prompting details.

### 9.3 GPT Failure Handling

If GPT scene splitting fails, the UI should show:

- Clear error message.
- Retry button.
- Option to edit/re-upload story.

The app must not proceed to image generation without a valid scene list.

---

## 10. Scene Review Flow

### 10.1 Scene Review Screen

After GPT returns the scene list, the user must review it.

The screen should show all scenes in order.

Each scene card should display:

- Scene number.
- Scene title.
- Scene summary.
- Characters detected.
- Location.
- Mood.
- Source excerpt.
- Draft visual prompt if available.

### 10.2 Required User Actions

The user must be able to:

- Edit scene title.
- Edit scene summary.
- Edit scene text or source excerpt.
- Edit detected characters.
- Edit draft prompt if shown.
- Delete incorrect scenes.
- Reorder scenes.
- Add a missing scene manually.
- Approve the final scene list.

### 10.3 Scene Validation Before Approval

Before approval, the system validates:

| Validation | Behavior |
|---|---|
| At least one scene exists | Block approval if none. |
| Scene numbers are ordered | Auto-renumber after reorder/delete. |
| Each scene has a summary | Block or warn if missing. |
| Characters referenced in scene have matching references | Warn or block depending on whether character is required. |
| Prompts are not empty if prompt generation already happened | Block generation if empty. |

### 10.4 Approval Rule

The app must require explicit approval.

Suggested primary action:

```text
Approve Scenes and Generate Prompts
```

The system must save approved scenes to:

```text
metadata/scenes.json
```

---

## 11. Prompt Generation Flow

### 11.1 Generate Prompts

After scene approval, the system generates final image prompts.

Prompt generation may use GPT to enrich:

- Visual composition.
- Anime style.
- Camera angle.
- Lighting.
- Character presence.
- Mood.
- Location.
- Outfit reminders.
- Negative prompt guidance.

### 11.2 Prompt Content Requirements

Each prompt should include:

| Prompt Part | Description |
|---|---|
| Scene visual description | What should be visible in the image. |
| Characters | Names and short visual reminders. |
| Composition | Framing, shot type, camera angle. |
| Style | Anime storyboard / anime illustration style. |
| Lighting and mood | Scene atmosphere. |
| Output format | Match selected preset/aspect ratio. |
| Character consistency hint | Reference image and IP-Adapter-FaceID usage metadata. |

### 11.3 Prompt Editing

Prompt editing should be supported if feasible in Phase 1.

If prompt editing is included, the user should be able to:

- Open a prompt per scene.
- Edit prompt text.
- Save changes.
- Reset to generated prompt.

If prompt editing is not included in the first MVP build, prompts must still be saved for debugging and future improvement.

Prompts must be saved to:

```text
metadata/prompts.json
```

---

## 12. Generation Settings Flow

### 12.1 Simple Settings

The default generation screen should show only simple settings.

Recommended simple settings:

| Setting | Default |
|---|---|
| Output preset | YouTube Standard — 1280x720 |
| Images per scene | 1 |
| Generation mode | Quality balanced |
| Character consistency | On when hardware supports it; low-VRAM fallback uses prompt-based hints |

### 12.2 Advanced Settings

Advanced settings may be hidden behind an expandable section.

Examples:

- Seed.
- Steps.
- Guidance scale.
- Scheduler.
- Model selection.
- IP-Adapter-FaceID strength.
- Negative prompt.
- Low VRAM mode.

The user should not need to open advanced settings to complete the normal flow.

### 12.3 Hardware Warning

If GPU/VRAM detection is available, the system should warn the user when selected settings may be too heavy.

Example:

```text
Your GPU may not have enough VRAM for this preset. Try Low VRAM Preview or SD 1.5 fallback.
```

---

## 13. Image Generation Flow

### 13.1 Start Generation

Primary action:

```text
Generate Images
```

Before generation starts, the system should confirm:

- Scene list is approved.
- Prompts exist.
- Required character references exist.
- Output folder is writable.
- Image generation model is available.

### 13.2 Generation Execution

For each approved scene, the system should:

1. Load the scene prompt.
2. Resolve characters present in the scene.
3. Load matching character reference images.
4. Apply IP-Adapter-FaceID for identity guidance when characters are present and hardware mode supports it.
5. If IP-Adapter-FaceID is disabled by low-VRAM mode, use prompt-based character hints instead.
6. Add outfit/style reminders through prompt text.
7. Generate image locally with Diffusers.
8. Save image with numeric scene prefix.
9. Update progress state.
10. Append result to output manifest.

### 13.3 Progress UI

The generation screen should show:

- Current scene number.
- Total scene count.
- Current scene title.
- Current status.
- Generated preview when available.
- Error state if a scene fails.

Example:

```text
Generating scene 3 of 12 — Dark Hallway
```

### 13.4 Per-Scene Failure Handling

If one scene fails, the app should not destroy completed outputs.

Recommended behavior:

- Mark failed scene as failed.
- Save error in logs.
- Allow retry for failed scene.
- Allow user to continue reviewing completed outputs.

### 13.5 Cancellation

If cancellation is supported, the system should:

- Finish or safely stop current generation task.
- Preserve already generated images.
- Mark remaining scenes as not generated.
- Save partial manifest.

---

## 14. Output Review Flow

### 14.1 Generation Complete Screen

After generation completes, the UI should show:

- Number of successful images.
- Number of failed scenes, if any.
- Output folder path.
- Preview grid of generated images.
- Button to open output folder.
- Button to retry failed scenes if any.

### 14.2 Output Folder

Generated images must be saved to:

```text
projects/{project_id}/outputs/images/
```

Example:

```text
001_akira_enters_school.png
002_hana_warning.png
003_dark_hallway.png
```

### 14.3 Manifest

The system must save a manifest:

```text
projects/{project_id}/outputs/manifest.json
```

The manifest should map each output image to:

- Project ID.
- Scene ID.
- Scene number.
- Scene title.
- Prompt ID.
- Character references used.
- Output filename.
- Generation status.
- Generation settings.
- Created timestamp.

---

## 15. Existing Project Flow

### 15.1 Open Existing Project

The user may open an existing local project.

The app should read:

```text
metadata/project.json
metadata/story.json
metadata/characters.json
metadata/scenes.json
metadata/prompts.json
metadata/generation_settings.json
outputs/manifest.json
```

### 15.2 Resume States

The app should support these project states:

| State | User can do |
|---|---|
| Created | Upload story. |
| Story uploaded | Upload characters. |
| Characters uploaded | Split scenes. |
| Scenes generated | Review/edit scenes. |
| Scenes approved | Generate prompts or images. |
| Prompts generated | Generate images. |
| Generation partial | Retry failed/missing scenes. |
| Generation complete | Open output folder or regenerate scenes. |

---

## 16. Main Screen Map

Phase 1 should use a simple linear screen flow.

```text
Home
  ├── Create Project
  ├── Open Existing Project
  └── Project Dashboard
        ├── Upload Story
        ├── Upload Characters
        ├── Scene Review
        ├── Prompt Review / Prompt Generation
        ├── Generation Settings
        ├── Image Generation Progress
        └── Output Review
```

---

## 17. User Flow State Machine

```text
NEW_PROJECT
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

Failure states:

```text
STORY_UPLOAD_FAILED
CHARACTER_VALIDATION_FAILED
SCENE_SPLITTING_FAILED
PROMPT_GENERATION_FAILED
GENERATION_FAILED
GENERATION_PARTIAL
```

The app should allow recovery from failure states where practical.

---

## 18. UX Copy Guidelines

### 18.1 Good Copy

Use simple user-facing language.

Examples:

```text
Upload your story
Upload character images
Review your scenes
Generate storyboard images
Open output folder
```

### 18.2 Avoid Technical Copy in Default Flow

Avoid exposing terms like these in the normal path:

```text
Diffusers pipeline
SDXL checkpoint
IP-Adapter-FaceID embeddings
Guidance scale
Scheduler
VRAM optimization
```

These can appear in logs, developer docs, or advanced settings.

### 18.3 Character Consistency Copy

Good user-facing wording:

```text
Character consistency helps the app keep faces and visual identity closer to your uploaded references.
```

Avoid overpromising:

```text
This guarantees the same face in every image.
```

---

## 19. Acceptance Criteria

### 19.1 Project and Upload Flow

- User can create a local project.
- User can upload a `.md` story file.
- User can preview uploaded story content.
- User can upload one or more character reference images.
- Character image filenames are validated against character names.

### 19.2 Scene Flow

- System can split a free-form story into ordered scenes using GPT.
- User can review all generated scenes before image generation.
- User can edit, delete, reorder, and approve scenes.
- Image generation cannot start before scene approval.

### 19.3 Prompt Flow

- System can generate prompts for approved scenes.
- Prompts are saved locally.
- Prompt data references the relevant scene and character names.

### 19.4 Generation Flow

- System can generate anime-style images locally using Diffusers.
- System uses IP-Adapter-FaceID for character identity guidance when character references are available.
- Output images are saved with numeric prefixes preserving story order.
- Generated output is saved in the local project folder.
- Manifest is created or updated after generation.

### 19.5 Recovery Flow

- Failed scene splitting can be retried.
- Failed image generation for a scene can be retried without deleting successful outputs.
- Existing projects can be reopened from local storage.

---

## 20. Non-Goals in User Flow

Do not include the following in the Phase 1 user flow:

- Video generation.
- Audio generation.
- Voice cloning.
- Lip-sync.
- Subtitle generation.
- Full video auto-editing.
- CapCut/Premiere/DaVinci timeline export.
- User accounts.
- Cloud rendering.
- Multi-user collaboration.
- Node graph editing.
- Advanced LoRA training.

---

## 21. Notes for Later Documents

The following areas should be expanded in later docs:

| Future doc | Detail to define |
|---|---|
| `docs/03-story-input-spec.md` | Exact story parsing expectations and input limits. |
| `docs/04-character-reference-spec.md` | Character image requirements, filename rules, IP-Adapter-FaceID input behavior. |
| `docs/05-scene-splitting-and-prompting-spec.md` | GPT prompt contracts, scene JSON schema, prompt JSON schema. |
| `docs/06-techstack.md` | Exact libraries and model package choices. |
| `docs/09-generation-pipeline.md` | Diffusers + SDXL + IP-Adapter-FaceID generation pipeline. |
| `docs/10-data-storage-spec.md` | Project state files and manifest schemas. |
| `AGENTS.md` | Guardrails for Codex Agent implementation. |

---

## 22. Final Phase 1 Flow Summary

```text
User opens local app
→ creates project
→ uploads story.md
→ uploads character reference images
→ system validates inputs
→ GPT splits story into ordered scenes
→ user reviews and edits scenes
→ user approves scene list
→ GPT generates image prompts
→ Diffusers generates images locally using character references and IP-Adapter-FaceID where hardware supports it, or prompt-based character hints in low-VRAM fallback mode
→ app saves ordered images and manifest locally
→ user opens output folder for manual editing
```
