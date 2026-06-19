# 05 — Scene Splitting and Prompting Spec

## 1. Document Purpose

This document defines how the Local AI Anime Storyboard Generator converts a free-form Markdown story into an ordered scene list and then into image-generation prompts.

This spec is intended for implementation by Codex Agent or another coding agent. It should be treated as the source of truth for:

- GPT scene splitting behavior.
- Scene JSON structure.
- Prompt generation behavior.
- User review and approval rules.
- Character-to-scene mapping.
- IP-Adapter-FaceID handoff for character consistency.
- Regeneration and error-handling behavior.

Phase 1 generates **images only**. Do not add video generation, voice, lip-sync, timeline export, or auto-editing behavior in this document.

---

## 2. Product Context

The user uploads:

1. A free-form `story.md` file.
2. One full-body image per main character.

The app then:

1. Reads and normalizes the story text.
2. Sends the story to GPT for scene splitting.
3. Receives an ordered scene list.
4. Shows the scene list to the user.
5. Requires the user to review, edit, reorder, delete, or approve scenes.
6. Generates image prompts only after scene approval.
7. Generates anime images locally using Diffusers.
8. Uses IP-Adapter-FaceID for best-effort character consistency when character references are present.
9. Saves ordered image assets to the local project folder.

The app must not generate images immediately after GPT scene splitting. Scene review is mandatory.

---

## 3. Core Rules

### 3.1 Free-Form Story Input

The app must support free-form Markdown story input.

The user is not required to write:

- Scene tags.
- Shot IDs.
- Character metadata blocks.
- Prompt syntax.
- JSON.
- YAML front matter.
- Any technical formatting.

The GPT scene splitter must infer scenes from prose, dialogue, action, location changes, emotional beats, and story progression.

### 3.2 Ordered Output Is Mandatory

Every generated scene must have a stable numeric order.

Scene order must be preserved across:

- `scenes.json`
- `prompts.json`
- UI review screen.
- Generation queue.
- Output image filenames.
- Output manifest.

The app must use 1-based display order for users and stable internal scene IDs for persistence.

Example output filenames:

```text
001_akira_enters_school.png
002_hana_warning.png
003_dark_hallway.png
```

### 3.3 User Review Is Mandatory

The app must not continue from scene splitting to image generation without explicit user approval.

The user must be able to:

- View scene order.
- View scene summary.
- View original source excerpt.
- View detected characters.
- View location and mood.
- Edit scene summary.
- Edit visual prompt.
- Delete incorrect scenes.
- Reorder scenes.
- Approve the scene list.

### 3.4 Character Consistency Approach

When a scene contains uploaded character references, the generation pipeline must use **IP-Adapter-FaceID** as the selected character consistency approach.

The prompting layer must prepare clear character metadata for the generation pipeline, but it must not promise perfect identity preservation.

Correct product wording:

```text
The app will try to preserve the character's face, outfit, and visual identity using the uploaded reference image and IP-Adapter-FaceID.
```

Avoid wording like:

```text
The character face will never change.
```

---

## 4. Inputs

### 4.1 Required Inputs

| Input | Source | Required | Description |
|---|---:|---:|---|
| `project_id` | App | Yes | Stable local project identifier. |
| `story.md` | User upload | Yes | Free-form Markdown story. |
| `normalized_story_text` | Story input service | Yes | Cleaned story text produced by `03-story-input-spec.md`. |
| `characters.json` | Character reference service | Optional but expected | Uploaded character references and filename mappings. |
| `output_preset` | Project settings | Yes | Default: YouTube Standard, 1280x720, 16:9. |
| `style_preset` | Project settings | Yes | Default anime storyboard style. |

### 4.2 Optional Inputs

| Input | Description |
|---|---|
| `user_scene_count_hint` | Optional rough scene count requested by the user. |
| `advanced_prompt_options` | Advanced settings hidden from non-technical users by default. |
| `negative_prompt_template` | Shared negative prompt for image generation. |
| `seed_policy` | Whether to use fixed, random, or per-scene seeds. |

---

## 5. Scene Splitting Pipeline

### 5.1 Pipeline Overview

```text
story.md
  ↓
Story Input Service
  ↓
normalized_story_text
  ↓
Scene Splitting Service
  ↓
draft scenes.json
  ↓
User Review UI
  ↓
approved scenes.json
  ↓
Prompt Generation Service
  ↓
prompts.json
  ↓
Generation Pipeline
```

### 5.2 Scene Splitting Steps

1. Load `normalized_story_text` from project metadata.
2. Load character names from `characters.json` if available.
3. Build a GPT request with:
   - Product context.
   - Story text.
   - Known character names.
   - Output JSON schema instructions.
   - Scene splitting rules.
4. Send request to the configured OpenAI model.
5. Parse GPT response as JSON.
6. Validate the JSON schema.
7. Normalize scene order and IDs.
8. Save draft `metadata/scenes.json`.
9. Show the review screen to the user.
10. Wait for explicit user approval before prompt generation.

---

## 6. GPT Model Decision

The intended model from product decisions is:

```text
gpt 5.4 mini
```

Implementation note:

- Treat this as the product-level intended model name.
- The final implementation must verify the exact OpenAI API model identifier before coding the client.
- The model name must be configurable through app settings or environment variables.

Recommended environment variable:

```env
OPENAI_SCENE_MODEL=gpt-5.4-mini
```

If the exact identifier differs, update the default value in code and docs together.

---

## 7. Scene Splitting Rules

### 7.1 Token and Context Limit Handling

`03-story-input-spec.md` allows up to 120,000 normalized characters. This can exceed or approach the practical context window of the configured OpenAI model depending on language and story density.

Implementation rule:

- Before sending the request, estimate token usage for story text plus instructions plus expected JSON output.
- If the story fits the configured model context window, send it as one request.
- If it does not fit, Phase 1 must either reject the story with a clear error or use a deterministic chapter/section chunking strategy that preserves order.
- The app must not truncate the story silently.
- If chunking is implemented, the merger must renumber scenes globally and preserve original story order.


### 7.2 What Counts as a Scene

A scene should usually represent one visual storytelling beat.

A new scene should be created when one or more of these changes occur:

- Location changes.
- Time changes.
- Major action changes.
- Character focus changes.
- Emotional beat changes.
- Camera framing would reasonably change.
- A new visual moment is needed for the storyboard.

### 7.3 Scene Granularity

The splitter should avoid both extremes:

- Too few scenes: one scene covers too much action and becomes visually vague.
- Too many scenes: every sentence becomes a separate image and generation becomes expensive.

Recommended default behavior:

```text
1 scene = 1 clear visual moment suitable for 1 generated anime image.
```

### 7.4 Dialogue Handling

Dialogue should be converted into visual moments.

The image prompt should not depend on rendering text bubbles or exact subtitles.

For example:

```text
Akira whispered, "Don't open that door."
```

Good scene summary:

```text
Akira stands in a dim hallway, tense and afraid, warning Hana not to open the old classroom door.
```

Bad scene prompt:

```text
Image with text: "Don't open that door."
```

Phase 1 should not generate speech bubbles, subtitles, or readable text inside images.

### 7.5 Internal Thoughts

Internal thoughts should be visualized as facial expression, pose, lighting, or atmosphere.

Example:

```text
Hana felt that something was watching her.
```

Good visual conversion:

```text
Hana glances over her shoulder in a deserted corridor, her face anxious, shadows stretching behind her.
```

### 7.6 Ambiguous Story Sections

When the story is ambiguous, GPT should make a reasonable storyboard interpretation without inventing major plot events.

Allowed:

- Infer a likely camera angle.
- Infer a mood from the text.
- Infer a simple environment if lightly implied.
- Condense repeated description.

Not allowed:

- Add new characters not present in the story.
- Add new plot twists.
- Change character relationships.
- Change the ending.
- Remove important story beats.

---

## 8. Scene JSON Schema

The scene splitter must output JSON only. No Markdown wrapper. No prose outside JSON.

The OpenAI request must enable JSON mode using `response_format: {"type": "json_object"}` or the current equivalent supported by the final OpenAI client. The text instruction alone is not sufficient.

### 8.1 Top-Level Shape

```json
{
  "project_id": "string",
  "story_title": "string | null",
  "language": "string",
  "scene_count": 3,
  "scenes": []
}
```

### 8.2 Scene Object Shape

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
  "visual_details": [
    "rusted gate",
    "orange sunset light",
    "empty school courtyard"
  ],
  "continuity_notes": [
    "Akira wears the same outfit as the uploaded reference image"
  ],
  "status": "draft"
}
```

### 8.3 Required Fields

Every scene must include:

- `scene_id`
- `scene_number`
- `title`
- `source_excerpt`
- `summary`
- `characters`
- `location`
- `time_of_day`
- `mood`
- `main_action`
- `camera_shot`
- `camera_angle`
- `visual_details`
- `continuity_notes`
- `status`

### 8.4 Field Rules

| Field | Rule |
|---|---|
| `scene_id` | Stable ID. Format: `scene_001`, `scene_002`, etc. |
| `scene_number` | 1-based order. Must be sequential. |
| `title` | Short user-facing title. Max recommended length: 80 chars. |
| `source_excerpt` | Direct short excerpt from story. Used for review/debugging. |
| `summary` | Human-readable scene summary. |
| `characters` | Names detected in the scene. Must prefer names from uploaded references. |
| `location` | Short visual location. |
| `time_of_day` | Example: morning, noon, dusk, night, unknown. |
| `mood` | Visual/emotional mood. |
| `main_action` | One primary visual action. |
| `camera_shot` | Example: close-up, medium shot, wide shot, establishing shot. |
| `camera_angle` | Example: eye level, low angle, high angle, over-the-shoulder. |
| `visual_details` | 3–8 concrete visual details. |
| `continuity_notes` | Outfit, face, prop, location, or scene continuity notes. |
| `status` | Initial value must be `draft`. |

### 8.5 Status Values

```text
draft
approved
needs_edit
skipped
generated
failed
```

Rules:

- GPT output must start with `draft`.
- User approval changes scene status to `approved`.
- Deleted scenes should either be removed or marked `skipped`, depending on storage design.
- Generated scenes should become `generated` after successful image generation.

---

## 9. Character Detection and Mapping

### 9.1 Known Character Names

The scene splitting service should pass known character names from uploaded image filenames to GPT.

Example uploaded files:

```text
Akira.png
Hana.png
Yuki.png
```

Known character list:

```json
["Akira", "Hana", "Yuki"]
```

GPT should prefer these names when filling `characters`.

### 9.2 Unknown Characters

If GPT detects a character in the story that has no uploaded reference image, it may include that character in the scene list, but the UI must surface a warning.

Example warning:

```text
Scene 4 includes "Teacher", but no matching character reference image was uploaded.
```

The user can then:

- Upload a matching reference image.
- Rename an existing reference.
- Remove the character from the scene.
- Continue without a reference for that character.

### 9.3 Matching Rule

Character matching must use the filename stem from uploaded image files.

Example:

```text
Akira.png → Akira
Hana.jpg → Hana
```

Matching should be case-insensitive for validation convenience, but stored canonical names should preserve the user-provided filename stem.

### 9.4 IP-Adapter-FaceID Handoff

The scene object should not directly store IP-Adapter-FaceID tensors, embeddings, or runtime objects.

Instead, `prompts.json` must include character reference metadata that the generation pipeline can resolve.

Example:

```json
{
  "character_references": [
    {
      "name": "Akira",
      "reference_image_path": "input/characters/Akira.png",
      "consistency_method": "ip_adapter_faceid"
    }
  ]
}
```

The generation pipeline is responsible for loading the image and preparing IP-Adapter-FaceID inputs.

---

## 10. Prompt Generation Pipeline

### 10.1 Prompt Generation Timing

Prompts should be generated only after the scene list is approved.

Allowed flow:

```text
GPT splits scenes → user reviews scenes → user approves scenes → app generates prompts
```

Disallowed flow:

```text
GPT splits scenes → app immediately generates images
```

### 10.2 Prompt Sources

Prompt generation should use:

- Approved scene summary.
- Scene visual details.
- Scene location.
- Scene mood.
- Scene camera shot and angle.
- Detected characters.
- Character reference metadata.
- Output preset.
- Shared anime style preset.
- Negative prompt template.

### 10.3 Prompt Object Shape

`metadata/prompts.json` should use this shape:

```json
{
  "project_id": "string",
  "prompt_version": 1,
  "style_preset": "anime_storyboard_default",
  "output_preset": {
    "name": "YouTube Standard",
    "width": 1280,
    "height": 720,
    "aspect_ratio": "16:9"
  },
  "prompts": []
}
```

### 10.4 Per-Scene Prompt Shape

```json
{
  "scene_id": "scene_001",
  "scene_number": 1,
  "positive_prompt": "anime storyboard illustration, cinematic wide shot, Akira entering an abandoned school gate at dusk, tense atmosphere, rusted gate, orange sunset light, empty courtyard, detailed background, clean line art, expressive face, consistent outfit",
  "negative_prompt": "low quality, blurry, distorted face, extra fingers, bad hands, text, watermark, logo, duplicate character, inconsistent outfit",
  "characters": [
    {
      "name": "Akira",
      "reference_image_path": "input/characters/Akira.png",
      "consistency_method": "ip_adapter_faceid",
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
  "status": "ready"
}
```

Default generation-setting rule:

- `docs/09-generation-pipeline.md` is the final source of truth for generation defaults once it exists.
- Until that document is written, prompt metadata must not leave `guidance_scale` or `num_inference_steps` as `null`.
- Temporary Phase 1 balanced defaults are `guidance_scale = 7.0` and `num_inference_steps = 30`.
- Low-VRAM mode may override these defaults in `generation_settings.json`, but the chosen numeric values must be explicit.

### 10.5 Prompt Style Requirements

Positive prompts should include:

- Anime/storyboard style.
- Main characters.
- Primary action.
- Location.
- Mood.
- Camera shot.
- Camera angle.
- Lighting.
- Key visual details.
- Continuity notes.

Positive prompts should avoid:

- Overly long prose.
- Complex plot explanation.
- Dialogue text.
- Speech bubble instructions.
- Requesting readable text in image.
- Contradictory camera directions.

### 10.6 Negative Prompt Defaults

Recommended default negative prompt:

```text
low quality, blurry, pixelated, distorted face, asymmetrical eyes, bad anatomy, bad hands, extra fingers, missing fingers, duplicate character, inconsistent outfit, inconsistent hairstyle, text, subtitle, speech bubble, watermark, logo, cropped face, cropped body
```

The negative prompt may be stored globally in `generation_settings.json` and copied into each prompt at generation time.

---

## 11. Prompt Editing Rules

### 11.1 User Editing

The user should be able to edit generated prompts before generation, but the UI should keep the basic experience simple.

Default UI:

- Show scene summary.
- Show characters.
- Show an expandable “Advanced prompt” section.

Advanced UI:

- Edit positive prompt.
- Edit negative prompt.
- Regenerate prompt from scene.
- Reset prompt to generated default.

### 11.2 Regenerating Prompts

If a user edits scene summary, visual details, camera shot, or characters, prompt status should become stale.

Example:

```json
{
  "prompt_status": "stale",
  "stale_reason": "scene_updated_after_prompt_generation"
}
```

The UI should offer:

```text
Regenerate prompt from updated scene
```

### 11.3 Manual Prompt Protection

If the user manually edits a prompt, the app should not overwrite it automatically.

Recommended field:

```json
{
  "manual_edit": true
}
```

When `manual_edit = true`, prompt regeneration should require explicit confirmation.

---

## 12. GPT Request Design

### 12.1 Scene Splitting System Instruction

The scene splitting request must use OpenAI JSON mode:

```json
{
  "response_format": { "type": "json_object" }
}
```

Use the current equivalent if the final OpenAI SDK version names this option differently.

The scene splitting request should tell GPT:

```text
You are an anime storyboard planner. Convert a free-form story into an ordered list of visual scenes for image generation. Each scene must represent one clear visual moment. Preserve story order. Do not invent major plot events. Return JSON only.
```

### 12.2 Scene Splitting User Payload

Recommended payload shape before sending to OpenAI:

```json
{
  "project_id": "project_123",
  "known_characters": ["Akira", "Hana"],
  "story_text": "...normalized story text...",
  "requirements": {
    "output_format": "json_only",
    "phase": "image_only_storyboard",
    "preserve_order": true,
    "require_visual_scenes": true,
    "avoid_dialogue_text_in_images": true
  }
}
```

### 12.3 Prompt Generation System Instruction

The prompt generation request must also use OpenAI JSON mode:

```json
{
  "response_format": { "type": "json_object" }
}
```

The prompt generation request should tell GPT:

```text
You are an anime image prompt engineer for a local Diffusers pipeline. Convert approved storyboard scenes into concise image-generation prompts. Preserve character names and scene order. Do not create video prompts. Do not request speech bubbles, subtitles, watermarks, or readable text. Return JSON only.
```

### 12.4 Prompt Generation User Payload

```json
{
  "project_id": "project_123",
  "approved_scenes": [],
  "characters": [],
  "output_preset": {
    "name": "YouTube Standard",
    "width": 1280,
    "height": 720,
    "aspect_ratio": "16:9"
  },
  "character_consistency": {
    "method": "ip_adapter_faceid",
    "mode": "best_effort"
  }
}
```

---

## 13. Validation Rules

### 13.1 Scene JSON Validation

The app must validate:

- Response is valid JSON.
- Top-level `scenes` exists and is an array.
- Scene count matches array length.
- Every scene has required fields.
- `scene_number` is sequential.
- `scene_id` is unique.
- `characters` is an array.
- No scene has an empty summary.
- No scene has a non-draft status from GPT output.

### 13.2 Prompt JSON Validation

The app must validate:

- Response is valid JSON.
- Prompt count matches approved scene count.
- Every prompt maps to an approved `scene_id`.
- Every prompt has `positive_prompt` and `negative_prompt`.
- Width and height match selected output preset.
- `consistency_method` equals `ip_adapter_faceid` for referenced characters.
- No video-specific prompt fields are present.

### 13.3 Validation Failure Behavior

If GPT output fails validation:

1. Save raw GPT response to logs for debugging.
2. Show a friendly error to the user.
3. Allow retry.
4. Do not mark scenes as approved.
5. Do not start image generation.

---

## 14. Storage Files

### 14.1 scenes.json

Path:

```text
projects/{project_id}/metadata/scenes.json
```

Stores:

- Draft scenes after GPT scene splitting.
- User edits.
- Scene approval state.
- Scene ordering.

### 14.2 prompts.json

Path:

```text
projects/{project_id}/metadata/prompts.json
```

Stores:

- Prompt version.
- Output preset snapshot.
- Positive and negative prompts.
- Character reference links.
- IP-Adapter-FaceID method metadata.
- Prompt status.

### 14.3 generation_settings.json

Path:

```text
projects/{project_id}/metadata/generation_settings.json
```

Stores:

- Selected model/pipeline settings.
- Output preset.
- Default negative prompt.
- Seed policy.
- Advanced settings.

---

## 15. UI Requirements

### 15.1 Scene Review Screen

The review screen must show:

- Scene number.
- Scene title.
- Scene summary.
- Characters detected.
- Location.
- Mood.
- Source excerpt.
- Warnings.
- Edit controls.
- Delete/skip controls.
- Reorder controls.
- Approve button.

### 15.2 Warnings

The UI should show warnings for:

- Character detected with no reference image.
- Scene has no detected character.
- Scene summary is too vague.
- Prompt is stale after scene edit.
- Prompt references a missing character image.
- GPT output had to be repaired or normalized.

### 15.3 Non-Technical UX

The default UI should avoid exposing:

- CFG scale.
- Sampler names.
- IP-Adapter-FaceID internals.
- CUDA settings.
- Embedding details.
- Diffusion pipeline internals.

These may appear only under an Advanced section if implemented.

---

## 16. Error Codes

| Code | Meaning | User-facing behavior |
|---|---|---|
| `SCENE_SPLIT_FAILED` | OpenAI request failed or returned unusable output. | Show retry option. |
| `SCENE_JSON_INVALID` | GPT response was not valid JSON. | Ask user to retry scene splitting. |
| `SCENE_SCHEMA_INVALID` | JSON did not match required schema. | Ask user to retry; log details. |
| `SCENE_APPROVAL_REQUIRED` | User tried to generate without approving scenes. | Redirect to review screen. |
| `PROMPT_GENERATION_FAILED` | Prompt generation failed. | Show retry option. |
| `PROMPT_JSON_INVALID` | Prompt response was not valid JSON. | Ask user to retry prompt generation. |
| `PROMPT_SCHEMA_INVALID` | Prompt JSON did not match schema. | Log and retry. |
| `CHARACTER_REFERENCE_MISSING` | Scene references a character without uploaded image. | Show warning; allow continue or upload image. |
| `PROMPT_STALE` | Scene changed after prompt generation. | Ask user to regenerate prompt. |
| `OPENAI_API_KEY_MISSING` | API key is not configured. | Show setup instructions. |

---

## 17. Logging Requirements

The app should log:

- Scene splitting request metadata, excluding full API key.
- Model identifier used.
- Token usage if available.
- Scene count returned.
- Validation errors.
- Prompt generation request metadata.
- Prompt count returned.
- Retry attempts.

The app should not log:

- OpenAI API key.
- Sensitive local paths beyond project-relative paths unless in debug mode.
- Large full raw story content repeatedly.

Raw GPT responses may be saved in debug logs only when validation fails.

---

## 18. Acceptance Criteria

### 18.1 Scene Splitting

- Given a valid `story.md`, the app can generate a draft ordered scene list.
- The scene list preserves story order.
- Each scene contains a clear visual summary.
- Each scene contains detected characters where possible.
- Scene JSON is saved to `metadata/scenes.json`.
- The user is taken to the scene review screen after splitting.

### 18.2 Mandatory Review

- The app does not generate images immediately after scene splitting.
- The user can edit scene summaries.
- The user can delete or skip incorrect scenes.
- The user can reorder scenes.
- The user must explicitly approve scenes before prompt generation.

### 18.3 Prompt Generation

- Given approved scenes, the app generates one prompt object per approved scene.
- Prompts preserve scene order.
- Prompts include positive and negative prompts.
- Prompts include output preset dimensions.
- Prompts include character reference metadata when characters have uploaded images.
- Character consistency metadata uses `ip_adapter_faceid`.
- Prompt JSON is saved to `metadata/prompts.json`.

### 18.4 Safety and Scope

- Prompt generation does not create video prompts.
- Prompt generation does not request subtitles, speech bubbles, or readable text.
- The app does not promise perfect face preservation.
- The app remains local-first and image-only for Phase 1.

---

## 19. Implementation Notes for Codex Agent

- Keep the scene splitter and prompt generator as separate services/modules.
- Use strict Pydantic models for scene and prompt schemas.
- Store project-relative paths, not absolute paths, in metadata files where possible.
- Make OpenAI model name configurable.
- Treat GPT output as untrusted until schema validation passes.
- Never start local Diffusers generation unless scenes are approved and prompts are valid.
- Keep IP-Adapter-FaceID setup inside the generation pipeline, not inside GPT parsing code.
- Avoid adding React, microservices, queues, cloud storage, or Docker-only workflows for Phase 1.

---

## 20. Out of Scope

The following are not part of this spec:

- Video generation.
- Voice generation.
- Subtitle generation.
- Lip-sync.
- CapCut/Premiere/DaVinci timeline export.
- Advanced LoRA training.
- Multi-user accounts.
- Cloud rendering.
- Real-time collaborative editing.
- Automatic publishing to YouTube or social platforms.

