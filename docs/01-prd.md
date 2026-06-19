# Local AI Anime Storyboard Generator — Product Requirements Document

**Document:** `docs/01-prd.md`  
**Product name:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Status:** Draft based on confirmed product decisions  
**Primary user:** Non-technical anime/story creator  

---

## 1. Product Overview

Local AI Anime Storyboard Generator is a local-first web application that helps creators turn a free-form Markdown story into ordered anime-style storyboard images.

The creator uploads:

1. A free-form `.md` story file.
2. One full-body character reference image per main character.

The app then:

1. Reads the story.
2. Uses GPT to split the story into ordered scenes.
3. Shows the generated scene list to the user for review.
4. Allows the user to edit, delete, reorder, and approve scenes.
5. Generates image prompts for approved scenes.
6. Generates anime-style images locally using Diffusers.
7. Saves all generated assets into a structured local project folder with strict scene ordering.

Phase 1 is focused on **image generation only**. It is not a full video generator.

---

## 2. Product Positioning

### 2.1 Recommended Positioning

> A local AI anime storyboard generator for creators. Upload a story and character references, review the auto-generated scene list, then generate ordered anime images ready for video editing.

### 2.2 Product Name for Phase 1

Use:

```text
Local AI Anime Storyboard Generator
```

Do not position Phase 1 as:

```text
Full AI Anime Video Generator
```

### 2.3 Future Product Direction

The future direction may become:

```text
Local AI Anime Video Generator
```

However, video generation is explicitly deferred and must not be implemented in Phase 1.

---

## 3. Problem Statement

Anime-style creators often have story ideas but struggle to convert them into consistent visual assets without learning complex AI tooling.

Existing AI image workflows often require users to understand:

- Prompt engineering.
- ComfyUI graphs.
- Diffusion model settings.
- GPU/VRAM configuration.
- Model selection.
- Manual scene planning.
- File organization.

This creates friction for non-technical creators who simply want to upload a story, upload character images, and receive ordered visual assets they can use for editing.

---

## 4. Goals

### 4.1 Product Goals

1. Let a non-technical creator generate ordered anime storyboard images from a free-form story.
2. Keep the workflow simple: upload story, upload character images, review scenes, generate images.
3. Avoid requiring structured scene tags in the story file.
4. Use GPT to perform story understanding, scene splitting, scene summarization, and prompt generation.
5. Require user review before image generation to reduce errors from automatic story parsing.
6. Preserve story order in all generated output files.
7. Keep all generated assets local on the user's machine.
8. Provide a default output preset suitable for YouTube-style desktop viewing.
9. Keep character consistency best-effort using one full-body reference image per character.
10. Keep Phase 1 architecture simple and local-first.

### 4.2 Engineering Goals

1. Build a local web UI app using FastAPI, Jinja2, and HTMX.
2. Prioritize Windows as the first supported OS.
3. Use local GPU when available for image generation.
4. Support CPU fallback, while clearly treating it as slow.
5. Use Diffusers + SDXL as the main image generation path.
6. Support SD 1.5 fallback if SDXL is too heavy for low VRAM machines.
7. Store project data and outputs in a structured local folder.
8. Avoid cloud rendering, multi-user accounts, message brokers, Docker-only workflows, or unnecessary infrastructure in Phase 1.

---

## 5. Non-Goals

The following are explicitly out of scope for Phase 1:

1. Video generation.
2. Voice generation.
3. Lip-sync.
4. Subtitle generation.
5. Auto-editing full videos.
6. Timeline export for CapCut, Premiere, or DaVinci.
7. Multi-user cloud server.
8. Account system.
9. Cloud rendering.
10. Real-time generation.
11. Advanced character LoRA training.
12. Complex node-based workflow editing.
13. React frontend.
14. Microservice architecture.
15. Message broker integration.

---

## 6. Target User

### 6.1 Primary User

The primary user is a non-technical creator who wants to create anime-style storyboard images from written stories.

This user may understand storytelling and video editing, but should not be expected to understand AI image generation internals.

### 6.2 User Skill Assumptions

The app must assume the user does **not** understand:

- Prompt engineering.
- Diffusion model internals.
- ComfyUI graphs.
- GPU settings.
- VRAM tuning.
- ControlNet configuration.
- Model checkpoints.
- Seed behavior.

### 6.3 Desired User Experience

The intended UX is:

```text
Upload story → upload character images → app splits scenes → user reviews scenes → click generate → get ordered image assets
```

---

## 7. User Personas

### 7.1 Solo Anime Story Creator

A creator writes short anime stories and wants to generate visual scenes for YouTube, TikTok, or other video platforms.

Needs:

- Simple upload flow.
- Automatic scene splitting.
- Editable scene list.
- Ordered image outputs.
- Consistent character appearance as much as possible.

Pain points:

- Does not want to manually write prompts for every scene.
- Does not want to learn ComfyUI.
- Needs files to be organized for later editing.

### 7.2 Re-editing / Storyboard Creator

A creator wants to prepare image assets first, then manually edit them later in video editing software.

Needs:

- Clear output folder.
- Stable image ordering.
- Useful image filenames.
- Manifest metadata.
- YouTube-friendly default aspect ratio.

---

## 8. Core User Journey

The confirmed Phase 1 workflow is:

```text
1. User opens local web UI.
2. User creates a project.
3. User uploads a free-form story.md file.
4. User uploads one full-body image per main character.
5. System validates character filenames.
6. System sends story content to GPT for scene splitting.
7. System generates ordered scene list.
8. User reviews and edits scene list.
9. User approves scene list.
10. System generates image prompts.
11. System generates anime images locally with Diffusers.
12. System saves generated images in strict story order.
13. User receives an output folder ready for manual editing.
```

---

## 9. Functional Requirements

## 9.1 Project Creation

### Requirement: Create Local Project

The app must allow the user to create a new local project.

Each project must have:

- Unique project ID.
- Project folder.
- Input folder.
- Character image folder.
- Metadata folder.
- Output image folder.
- Logs folder.

### Acceptance Criteria

- User can create a new project from the local web UI.
- App creates a local project folder automatically.
- Project metadata is stored locally.
- The user does not need to manually create folders.

---

## 9.2 Story Upload

### Requirement: Upload Free-form Markdown Story

The app must allow the user to upload a `.md` story file.

The story file must be free-form. The user must not be required to write structured scene tags.

### Acceptance Criteria

- User can upload one `.md` file per project.
- App stores the uploaded file under the project input folder.
- App can read story text from the uploaded file.
- App does not require scene markers, custom syntax, or templates.
- If the file is missing, empty, unreadable, or not Markdown, the app shows a clear error.

---

## 9.3 Character Reference Upload

### Requirement: Upload One Full-body Image Per Main Character

The app must allow the user to upload character reference images.

Each main character must have one full-body image.

The image should include:

- Face.
- Body.
- Outfit.
- Overall anime style.

### Requirement: Character Filename Matching

The character image filename must match the character name used in the story.

Example:

```text
Akira.png
Hana.png
Yuki.png
```

If the story contains a character named `Akira`, the app should look for a matching uploaded file named `Akira` with a supported image extension.

### Acceptance Criteria

- User can upload multiple character images.
- App stores character images under `input/characters/`.
- App validates that character filenames can be mapped to detected story characters.
- App warns the user when a detected character has no matching image.
- App warns the user when an uploaded character image is not used by any detected character.
- App does not promise perfect identity preservation.

---

## 9.4 Scene Splitting

### Requirement: GPT-based Scene Splitting

The app must send the story content to GPT for scene splitting.

The intended GPT model from product decision is:

```text
gpt 5.4 mini
```

The final techstack must verify the exact OpenAI API model identifier before implementation.

### Scene Splitting Output

The system should produce an ordered scene list containing:

- Scene number.
- Scene title.
- Scene summary.
- Source story excerpt or reference.
- Characters detected in the scene.
- Location or background if detectable.
- Mood or emotional tone if detectable.
- Suggested visual direction.
- Draft prompt or prompt notes.

### Acceptance Criteria

- App can split a free-form Markdown story into ordered scenes.
- Scene order follows story order.
- Scene list is saved to project metadata.
- Scene splitting errors are shown clearly.
- App does not continue to image generation automatically after scene splitting.

---

## 9.5 Mandatory Scene Review

### Requirement: User Must Review Scene List Before Generation

After GPT splits the story into scenes, the app must require the user to review and approve the scene list before image generation starts.

The user must be able to:

- View scene order.
- View scene summary.
- View characters detected in each scene.
- Edit scene text and visible scene-level visual notes.
- Delete incorrect scenes.
- Reorder scenes.
- Approve the final scene list.

### Acceptance Criteria

- App blocks image generation until the user approves the scene list.
- App clearly shows scene approval status.
- User edits are saved before generation starts.
- Deleted scenes are not generated.
- Reordered scenes affect final output numbering.

---

## 9.6 Prompt Generation

### Requirement: Generate Image Prompts for Approved Scenes

After the user approves the scene list, the app must generate image prompts for each approved scene.

Prompts should include:

- Scene summary.
- Characters in the scene.
- Character visual identity references.
- Background/location.
- Anime style direction.
- Mood.
- Camera framing.
- Lighting.
- Output aspect ratio.
- Negative prompt if useful.

### Acceptance Criteria

- Every approved scene gets a generated prompt.
- Prompt output is saved to metadata.
- Prompts preserve approved scene order.
- Prompts reference character names consistently.
- Prompt generation failure does not corrupt the project.

---

## 9.7 Image Generation

### Requirement: Generate Anime-style Images Locally

The app must generate anime-style images locally using Diffusers.

Default image generation engine:

```text
Diffusers + SDXL
```

Fallback:

```text
SD 1.5 base fallback if SDXL is too heavy
```

### Hardware Requirement

Minimum target:

```text
4GB VRAM
```

Important low-VRAM rule:

- 4GB VRAM is the minimum target for image-only generation with low-VRAM behavior, not a guarantee that SDXL + IP-Adapter-FaceID will run together.
- On 4GB VRAM machines, the app must default to a low-VRAM path: SD 1.5 fallback or lower-resolution preset.
- On 4GB VRAM machines, IP-Adapter-FaceID must be disabled by default unless hardware detection confirms it can run safely.
- When IP-Adapter-FaceID is disabled, generation must fall back to prompt-based character hints using the character name, outfit reminder, and reference-derived metadata already available.

CPU fallback may exist but is expected to be very slow.

### Acceptance Criteria

- App generates one image per approved scene by default.
- Images are generated locally on the user's machine.
- App uses GPU when available.
- App can expose advanced settings only under an advanced settings area.
- App saves generated images in strict scene order.
- Failed scene generation is logged and shown to the user.

---

## 9.8 Output Presets

### Requirement: YouTube-style Default Output

The default output should target YouTube-style desktop viewing and avoid looking broken, tiny, or heavily pixelated on a computer screen.

Default Phase 1 preset:

```text
YouTube Standard — 1280x720, 16:9
```

### Supported Presets

The app should support presets instead of forcing one fixed resolution.

Recommended presets:

```text
YouTube Standard: 1280x720
YouTube High: 1920x1080
Low VRAM Preview: 960x540
Square Preview: 1024x1024
Vertical Short: 1080x1920
```

Optional low VRAM fallback:

```text
768x432
```

### Acceptance Criteria

- New projects default to YouTube Standard.
- User can select another preset before generation.
- Selected preset is saved in generation settings metadata.
- Generated prompts and images use the selected aspect ratio.

---

## 9.9 Output Folder and File Ordering

### Requirement: Structured Local Output Folder

The app must save project files locally in a structured folder.

Recommended folder structure:

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
        003_scene.png
      manifest.json
    logs/
      app.log
      generation.log
```

### Requirement: Numeric Filename Prefixes

Generated image files must include numeric prefixes.

Example:

```text
001_akira_enters_school.png
002_hana_warning.png
003_dark_hallway.png
```

### Acceptance Criteria

- All generated images include numeric prefixes.
- Numeric prefixes reflect the approved scene order.
- Asset order remains stable in normal file explorers and video editors.
- Output folder contains a manifest describing generated assets.

---

## 9.10 Local Web UI

### Requirement: Simple Local Web UI

The app must run locally and open in the browser at a localhost URL.

Example:

```text
http://localhost:8000
```

Confirmed web stack:

```text
Backend: FastAPI
UI: Jinja2 + HTMX
```

### Acceptance Criteria

- User can start the app locally.
- User can access the app in a browser.
- UI supports the full core workflow.
- UI does not require account registration.
- UI does not expose unnecessary technical complexity by default.

---

## 10. Non-functional Requirements

## 10.1 Platform

- First supported OS: Windows.
- Implementation and setup scripts must prioritize Windows.
- The app may be portable to other OSes later, but Phase 1 must optimize for Windows.

## 10.2 Local-first Behavior

- Project files must be stored locally.
- Generated images must be stored locally.
- Image generation must run locally.
- No cloud rendering in Phase 1.
- No multi-user hosted server in Phase 1.

## 10.3 Usability

- Default workflow must be simple enough for a non-technical creator.
- Advanced model settings must be hidden under an advanced settings section.
- Errors must use plain language.
- The UI must clearly indicate the current step.

## 10.4 Performance

- GPU should be used when available.
- CPU generation can be supported but should be communicated as slow.
- The app should avoid freezing the UI during long-running generation.
- Generation progress should be visible to the user.

## 10.5 Reliability

- Story upload, character upload, scene metadata, prompts, and generated images must be saved safely.
- A failed generation step must not delete existing project files.
- The app should log generation errors for debugging.
- The user should be able to inspect which scenes succeeded and which failed.

## 10.6 Privacy

- Story files and generated images stay on the user's local machine.
- Story content is sent to OpenAI API for GPT-based scene splitting and prompt generation.
- The app must make this behavior clear in future UI copy.
- Local image generation should not upload generated images to a cloud renderer.

---

## 11. Character Consistency Requirement

### 11.1 Product Expectation

The app should aim for best-effort character consistency.

Use this product wording:

> The app should try to preserve the character's face, outfit, and visual identity based on the uploaded full-body reference image.

### 11.2 What Not to Promise

Do not promise:

> The face will never change.

Reason:

- With only one reference image per character, perfect identity lock is not technically guaranteed.
- Face and outfit may drift across scenes depending on pose, lighting, camera angle, and model behavior.

### 11.3 Phase 1 Outfit Assumption

Phase 1 assumes each character wears the same outfit throughout the story.

This reduces prompt complexity and improves visual consistency.

---

## 12. User-facing Workflow Requirements

The UI should be organized around clear steps:

1. Create project.
2. Upload story.
3. Upload character images.
4. Validate inputs.
5. Split story into scenes.
6. Review scenes.
7. Approve scenes.
8. Select output preset.
9. Generate images.
10. View output folder.

The app must not skip the review/approval step.

---

## 13. Data Requirements

Phase 1 should persist at least the following project data:

### 13.1 Project Metadata

- Project ID.
- Project name.
- Created timestamp.
- Updated timestamp.
- Project status.
- Selected output preset.

### 13.2 Story Metadata

- Original story filename.
- Stored story path.
- Story text checksum if useful.

### 13.3 Character Metadata

- Character name.
- Source filename.
- Stored image path.
- Validation status.

### 13.4 Scene Metadata

- Scene ID.
- Scene number.
- Scene title.
- Scene summary.
- Characters in scene.
- Source excerpt/reference.
- User-edited text if any.
- Approved status.
- Deleted status.

### 13.5 Prompt Metadata

- Scene ID.
- Prompt text.
- Negative prompt.
- Prompt generation timestamp.
- Model used for prompt generation.

### 13.6 Image Output Metadata

- Scene ID.
- Output filename.
- Output path.
- Width.
- Height.
- Seed if available.
- Generation model.
- Generation status.
- Error message if failed.

---

## 14. MVP Success Criteria

The Phase 1 MVP is successful when:

1. A user can launch the app locally on Windows.
2. A user can create a project.
3. A user can upload a free-form Markdown story.
4. A user can upload character reference images.
5. The app can split the story into ordered scenes using GPT.
6. The user can review, edit, reorder, delete, and approve scenes.
7. The app can generate prompts for approved scenes.
8. The app can generate anime-style images locally.
9. The app saves images with numeric prefixes preserving scene order.
10. The app stores metadata and outputs in a structured project folder.
11. The app does not implement video generation or cloud rendering.

---

## 15. Phase 1 Guardrails

The following guardrails are mandatory:

1. Phase 1 is image only.
2. Do not implement video generation.
3. Do not require structured scene tags in story input.
4. Do not start generation before user scene approval.
5. Use one full-body image per character.
6. Map character references by filename.
7. Treat character consistency as best effort.
8. Prioritize Windows.
9. Keep the app local-first.
10. Preserve output order using numeric filename prefixes.
11. Keep architecture simple: FastAPI + Jinja2 + HTMX.
12. Do not introduce React, microservices, Docker-only workflows, message brokers, or hosted infrastructure unless explicitly approved later.

---

## 16. Risks and Mitigations

### 16.1 Risk: GPT Scene Splitting Is Imperfect

Mitigation:

- Make scene review mandatory.
- Allow edit, delete, and reorder before generation.

### 16.2 Risk: Character Identity Drift

Mitigation:

- Use full-body reference images.
- Include character identity details in prompts.
- Use best-effort wording.
- Avoid promising perfect face preservation.

### 16.3 Risk: Low VRAM Machines Cannot Run SDXL + IP-Adapter-FaceID Reliably

Mitigation:

- Treat 4GB VRAM as a low-VRAM minimum target, not a full-quality SDXL + IP-Adapter-FaceID target.
- Provide low VRAM presets.
- Support SD 1.5 fallback if SDXL is too heavy.
- Disable IP-Adapter-FaceID by default on 4GB VRAM machines and use prompt-based character hints instead.
- Communicate CPU fallback as slow.

### 16.4 Risk: Non-technical Users Feel Overwhelmed

Mitigation:

- Keep default UI simple.
- Hide advanced settings.
- Use step-by-step workflow.
- Show plain-language errors.

### 16.5 Risk: Output Assets Become Disorganized

Mitigation:

- Enforce structured project folder.
- Use numeric filename prefixes.
- Save manifest metadata.

---

## 17. Open Questions

These are not blockers for the PRD, but should be resolved before implementation polish:

1. Exact OpenAI API model identifier for `gpt 5.4 mini`.
2. Final SDXL model choice.
3. Whether SD 1.5 fallback is included in first MVP or immediately after MVP.
4. Whether GPU auto-detection is included in the first build.
5. Whether image upscaling is included in Phase 1.
6. Whether generated scene prompts are editable by the user in first MVP.
7. Whether project history is stored in SQLite or only local JSON files.
8. Whether packaging starts as a `.bat` startup script or a full Windows installer.

---

## 18. Implementation Notes for Later Docs

This PRD intentionally avoids locking low-level implementation details that belong in later documents.

Details should be expanded in:

- `docs/02-user-flow.md`
- `docs/03-story-input-spec.md`
- `docs/04-character-reference-spec.md`
- `docs/05-scene-splitting-and-prompting-spec.md`
- `docs/06-techstack.md`
- `docs/07-architecture.md`
- `docs/08-api-spec.md`
- `docs/09-generation-pipeline.md`
- `docs/10-data-storage-spec.md`
- `docs/11-project-structure.md`
- `docs/12-error-handling-logging.md`
- `docs/13-testing-strategy.md`
- `docs/14-mvp-task-breakdown.md`

---

## 19. Final Phase 1 Definition

Phase 1 is complete when the app can turn a free-form story and character reference images into locally generated, ordered anime storyboard images, with mandatory user scene review before generation.

