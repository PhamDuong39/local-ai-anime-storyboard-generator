# 00 — Product Decisions

## Product

**Product name:** Local AI Anime Storyboard Generator

**Phase 1 positioning:** A local AI anime storyboard generator for creators. Users upload a story and character references, review an auto-generated scene list, then generate ordered anime images that are ready for manual video editing.

**Future direction:** Local AI Anime Video Generator.

**Important naming rule:** Phase 1 must not be positioned as a full AI anime video generator. Phase 1 is image/storyboard generation only.

---

## 1. Product Decision Summary

The app is a **local AI anime storyboard/image generator**.

The user provides:

- One free-form Markdown story file.
- One full-body reference image for each main character.

The app will:

1. Read the uploaded story.
2. Use GPT to split the story into ordered scenes.
3. Let the user review and edit the generated scene list.
4. Generate prompts for the approved scenes.
5. Generate anime-style images locally using Diffusers.
6. Save generated assets into a structured local project folder.
7. Preserve strict story order in filenames and metadata.

Phase 1 focuses only on ordered image assets. The output is intended for creators who will later edit the generated images manually in tools such as CapCut, Premiere, DaVinci Resolve, or similar editors.

---

## 2. Phase 1 Scope Decisions

### 2.1 In Scope

Phase 1 includes:

- Local web UI app.
- Windows-first setup and runtime.
- Running on the user's own machine.
- Local GPU/CPU-based image generation.
- Free-form `.md` story upload.
- Character reference image upload.
- GPT-based story understanding.
- GPT-based scene splitting.
- GPT-based scene summarization.
- GPT-based prompt generation and prompt enrichment.
- Mandatory user review before generation.
- Ordered anime image generation.
- Structured local output folder.
- Numeric filename prefixes to preserve scene order.
- Simple UX for non-technical creators.

### 2.2 Out of Scope

Phase 1 excludes:

- Video generation.
- Voice generation.
- Lip-sync.
- Subtitle generation.
- Auto-editing full videos.
- Timeline export for CapCut, Premiere, or DaVinci Resolve.
- Multi-user cloud server.
- Account system.
- Cloud rendering.
- Real-time generation.
- Advanced character LoRA training.
- Complex ComfyUI-style workflow editing.
- React frontend.
- Microservices.
- Message brokers.
- Docker-only workflow.

### 2.3 Scope Rule

Any feature that moves the product toward full video generation, hosted infrastructure, multi-user accounts, or advanced AI workflow editing must be deferred unless explicitly approved later.

---

## 3. Target User Decision

The first target user is a **non-technical creator**.

The user should not need to understand:

- Prompt engineering.
- ComfyUI graphs.
- Diffusion model internals.
- GPU settings.
- AI workflow configuration.
- Python scripts.
- Model pipeline tuning.

The intended UX is:

```text
Upload story → upload character images → app splits scenes → user reviews scenes → click generate → get ordered image assets
```

### UX Principle

The product should feel like a guided creator tool, not an AI engineering dashboard.

Advanced settings may exist later, but they must be hidden under an explicit advanced section and should never block the basic workflow.

---

## 4. Platform and Runtime Decisions

### 4.1 First Target OS

The first supported OS is:

```text
Windows
```

Even though the app is a local web UI, Windows matters because local AI generation depends on:

- GPU driver setup.
- CUDA and PyTorch installation.
- File path handling.
- Local model storage.
- Startup scripts.
- Packaging and installation.
- User expectations for a desktop-style local tool.

### 4.2 App Type

The app is a **local web UI**.

Confirmed stack direction:

```text
Backend: FastAPI
UI: Jinja2 + HTMX
Runtime: localhost browser app
```

Expected local URL pattern:

```text
http://localhost:8000
```

### 4.3 Architecture Simplicity Rule

Keep the Phase 1 architecture simple.

Do not introduce:

- React.
- Next.js.
- Microservices.
- Kafka or other message brokers.
- Cloud rendering infrastructure.
- Hosted account systems.
- Docker-only setup.


---

## 5. AI and Model Decisions

### 5.1 GPT Usage

GPT is used for:

- Story understanding.
- Scene splitting.
- Scene summarization.
- Character detection per scene.
- Prompt generation.
- Prompt enrichment.

### 5.2 Scene Splitting Model

The intended GPT model for scene splitting is:

```text
gpt 5.4 mini
```

Implementation note:

The final tech stack must verify the exact OpenAI API model identifier before implementation. Treat `gpt 5.4 mini` as the product decision name until the actual API identifier is confirmed.

### 5.3 Image Generation Engine

The image generation engine is:

```text
Diffusers + SDXL
```

The app should use the user's local GPU when available.

CPU fallback may exist, but it is expected to be very slow and should be treated as a fallback, not the recommended path.

### 5.4 Minimum Hardware Target

Minimum target:

```text
4GB VRAM
```

Phase 1 must support image-only generation. If SDXL is too heavy for the user's machine, an SD 1.5 base fallback should be considered.

### 5.5 Character Consistency Expectation

Character consistency is **best effort**.

Allowed product promise:

```text
The app should try to preserve the character's face, outfit, and visual identity based on the uploaded full-body reference image.
```

Forbidden product promise:

```text
The face will never change.
```

Reason:

With only one reference image per character, perfect identity lock is not technically guaranteed. Face, outfit, and visual details may drift across scenes because of pose, lighting, camera angle, generation seed, and model behavior.

---

## 6. Output Preset Decisions

### 6.1 Default Output Target

The default output should target **YouTube-style desktop viewing**.

The generated image should not look broken, tiny, or heavily pixelated on a computer screen.

### 6.2 Default Phase 1 Preset

The default preset is:

```text
YouTube Standard — 1280x720, 16:9
```

### 6.3 Supported Preset Direction

The implementation should provide presets instead of forcing one fixed resolution.

Recommended presets:

```text
YouTube Standard: 1280x720
YouTube High: 1920x1080
Low VRAM Preview: 960x540
Square Preview: 1024x1024
Vertical Short: 1080x1920
```

### 6.4 Low VRAM Handling

For low VRAM machines, the app may support lower generation sizes such as:

```text
960x540
768x432
```

Optional upscaling can be considered later, but it is not required unless explicitly added to Phase 1.

---

## 7. Story Input Decisions

### 7.1 Input Format

The story input is a free-form Markdown file:

```text
story.md
```

The user is not required to write structured scene tags.

### 7.2 Scene Splitting

The app must automatically split the story into scenes using GPT.

Scene splitting should preserve:

- Story order.
- Character appearances.
- Scene context.
- Important dialogue or action beats.
- Visual continuity where possible.

### 7.3 Mandatory Scene Review

After GPT splits the story into scenes, the user must review the scene list before image generation starts.

The app must allow the user to:

- View scene order.
- View scene summary.
- View detected characters per scene.
- Edit scene text if needed.
- Edit generated prompt if prompt editing is enabled.
- Delete incorrect scenes.
- Reorder scenes.
- Approve the final scene list.

### 7.4 Hard Rule

The app must not start image generation immediately after GPT scene splitting.

Scene review and approval are mandatory because free-form story parsing can be imperfect.

---

## 8. Character Reference Decisions

### 8.1 Character Image Rule

Each main character must have one full-body image.

The character image should include:

- Face.
- Body.
- Outfit.
- Overall anime style.

### 8.2 Filename Matching Rule

The character image filename must match the character name used in the story.

Example:

```text
Akira.png
Hana.png
Yuki.png
```

If the story contains a character named `Akira`, the app should look for an uploaded character reference file named `Akira`.

Allowed extensions should be defined later in the character reference spec, but expected image formats include:

```text
.png
.jpg
.jpeg
.webp
```

### 8.3 Outfit Consistency Rule

Phase 1 assumes each character wears the same outfit throughout the story.

This reduces prompt complexity and improves consistency across generated images.

### 8.4 Character Mapping Rule

One character equals one reference image.

The app should not require multiple reference images, LoRA training, or complex identity setup in Phase 1.

---

## 9. Core Workflow Decision

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

### Workflow Invariant

The following order must not be broken:

```text
Story upload → character upload → scene split → user review → approval → prompt generation → image generation → ordered export
```

---

## 10. Output Folder Decisions

### 10.1 Local Output Requirement

Output must be:

- Local.
- Structured.
- Ordered.
- Easy to inspect manually.
- Easy to import into video editing software.

### 10.2 Recommended Project Folder Structure

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
      scenes.json
      prompts.json
      generation_settings.json
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

### 10.3 Generated Filename Rule

Generated image files must include numeric prefixes.

Examples:

```text
001_akira_enters_school.png
002_hana_warning.png
003_dark_hallway.png
```

This prevents asset order from being shuffled during manual editing.

### 10.4 Manifest Rule

The output should include a manifest file that maps generated files back to scene metadata.

Recommended manifest path:

```text
outputs/manifest.json
```

The manifest should include at minimum:

- Project ID.
- Scene ID.
- Scene index.
- Scene title or short slug.
- Output image filename.
- Prompt reference.
- Generation settings reference.
- Created timestamp.

---

## 11. Product Guardrails

These guardrails must be respected across all later docs and implementation tasks.

### Guardrail 1 — Phase 1 Is Image Only

Do not implement video generation in Phase 1.

### Guardrail 2 — Non-Technical Creator First

Do not expose complex model settings unless they are placed under an advanced settings section.

### Guardrail 3 — Free-Form Story Input

Do not require users to write structured scene tags.

### Guardrail 4 — Mandatory Scene Review

The app must not start image generation immediately after GPT scene splitting. The user must review and approve scenes first.

### Guardrail 5 — One Character Equals One Full-Body Image

Each character must be mapped by filename to exactly one full-body reference image.

### Guardrail 6 — Best-Effort Character Consistency

Do not promise perfect face preservation.

### Guardrail 7 — Windows First

Implementation, setup scripts, and packaging should prioritize Windows.

### Guardrail 8 — Local First

Do not design cloud rendering, multi-user accounts, or hosted infrastructure for Phase 1.

### Guardrail 9 — Ordered Output Is Mandatory

Every generated image must preserve scene order using numeric filename prefixes.

### Guardrail 10 — Keep Architecture Simple

Use FastAPI + Jinja2 + HTMX. Do not introduce unnecessary infrastructure unless explicitly approved later.

---

## 12. Open Questions

These questions are not blockers for documentation, but should be resolved before implementation polish.

1. What is the exact OpenAI API model identifier for `gpt 5.4 mini`?
2. Which exact SDXL model should be used by default?
3. Should SD 1.5 fallback be included in the first MVP or immediately after MVP?
4. Should GPU auto-detection be included in the first build?
5. Should image upscaling be included in Phase 1?
6. Should generated scene prompts be editable by the user?
7. Should project history be stored in SQLite or only local JSON files?
8. Should packaging start with a simple `.bat` startup script or a full Windows installer?

---

## 13. Decisions Not to Reopen Without Explicit Approval

The following decisions are considered locked for Phase 1:

- Product is local-first.
- Target OS is Windows first.
- UI is local web UI.
- Backend is FastAPI.
- UI framework is Jinja2 + HTMX.
- Phase 1 generates images only.
- Story input is free-form Markdown.
- GPT handles scene splitting.
- User must review scenes before generation.
- Image generation uses Diffusers + SDXL direction.
- Minimum hardware target is 4GB VRAM with possible SD 1.5 fallback.
- Character reference rule is one full-body image per main character.
- Character filename must match story character name.
- Character consistency is best effort.
- Default output preset is YouTube Standard, 1280x720, 16:9.
- Output must be local, structured, and numerically ordered.

---

## 14. How Future Docs Should Use This File

This file is the decision baseline for the rest of the documentation set.

Later docs must not contradict these decisions:

- `docs/01-prd.md` should expand product requirements from these decisions.
- `docs/02-user-flow.md` should detail the upload, review, generation, and export flow.
- `docs/03-story-input-spec.md` should define valid story input behavior.
- `docs/04-character-reference-spec.md` should define image validation and filename matching.
- `docs/05-scene-splitting-and-prompting-spec.md` should define GPT prompts, output schema, and review flow.
- `docs/06-techstack.md` should verify exact package and model identifiers.
- `docs/07-architecture.md` should keep the app local-first and simple.
- `AGENTS.md` should include the guardrails from this file.
