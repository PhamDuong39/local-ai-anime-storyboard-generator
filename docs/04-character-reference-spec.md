# Local AI Anime Storyboard Generator — Character Reference Specification

**Document:** `docs/04-character-reference-spec.md`  
**Product name:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Status:** Draft based on confirmed product decisions  
**Primary user:** Non-technical anime/story creator  

---

## 1. Purpose

This document defines how the app accepts, validates, stores, maps, and uses character reference images for local anime image generation.

Character references are required because Phase 1 must help the user generate ordered anime storyboard images where the same character remains visually recognizable across scenes.

The selected character consistency approach for Phase 1 documentation is:

```text
IP-Adapter-FaceID
```

This document is the source of truth for:

- Character reference upload rules.
- Filename-to-character-name mapping.
- Image quality expectations.
- Validation behavior.
- Character metadata format.
- IP-Adapter-FaceID usage expectations.
- User-facing consistency wording.
- Error cases and acceptance criteria.

---

## 2. Product Rules

### 2.1 One Main Character Equals One Reference Image

Each main character must have exactly one uploaded reference image in Phase 1.

The image should be a full-body image that clearly shows:

- Face.
- Hair.
- Body shape.
- Outfit.
- Overall anime style.
- Main visual identity.

The app should treat the uploaded image as the character's canonical visual reference for the project.

### 2.2 Filename Must Match Character Name

The uploaded character image filename must match the character name used in the story.

Examples:

```text
Akira.png
Hana.png
Yuki.png
```

If the story uses the character name `Akira`, the uploaded reference file should be named:

```text
Akira.png
```

This filename rule keeps the product simple for non-technical creators and avoids needing a complex character mapping UI in Phase 1.

### 2.3 Same Outfit Assumption

Phase 1 assumes each character wears the same outfit throughout the story.

This is a deliberate MVP simplification. It helps reduce prompt complexity and improves consistency across generated images.

Do not implement per-scene outfit changes in Phase 1 unless the product decision changes.

### 2.4 Best-Effort Consistency

The app must describe character consistency as **best effort**.

Allowed wording:

```text
The app will try to preserve the character's face, outfit, and visual identity using the uploaded reference image.
```

Do not promise:

```text
The face will never change.
The character will be perfectly identical in every image.
The outfit will never drift.
```

Reason:

Even with IP-Adapter-FaceID, perfect identity lock is not guaranteed across all poses, expressions, lighting, camera angles, seeds, prompts, and local model choices.

---

## 3. Supported Image Files

### 3.1 Accepted Extensions

Phase 1 should support these image formats:

```text
.png
.jpg
.jpeg
.webp
```

Recommended preferred format:

```text
.png
```

### 3.2 Unsupported Files

Do not accept these as character references in Phase 1:

```text
.gif
.bmp
.tiff
.svg
.psd
.heic
.avif
.pdf
.docx
.zip
```

### 3.3 MIME Type Handling

Validation should not rely only on MIME type because local browsers and operating systems may report files differently.

Recommended validation order:

1. Check file extension.
2. Try to open the file using Pillow or equivalent image loading library.
3. Confirm the image can be decoded.
4. Confirm dimensions are available.
5. Confirm the image is not empty, corrupt, or unreadable.
6. Save only after validation passes.

---

## 4. Character Filename Rules

### 4.1 Base Name Matching

The character name is derived from the filename without extension.

Example:

```text
Akira.png → Akira
Hana.jpg → Hana
Yuki.webp → Yuki
```

### 4.2 Case Sensitivity

For user experience, the UI may perform case-insensitive suggestions, but the stored canonical character name should preserve the filename casing.

Example:

```text
akira.png
```

can be suggested as a possible match for story character:

```text
Akira
```

However, the app should recommend renaming the file to:

```text
Akira.png
```

### 4.3 Spaces and Special Characters

Phase 1 should support simple names first.

Recommended filename pattern:

```text
CharacterName.png
```

Allowed examples:

```text
Akira.png
Hana.png
Yuki.png
Mai_Sakura.png
Ren-Takeda.png
```

Avoid requiring support for complicated filenames like:

```text
Akira final version (new)!!.png
main-char@episode1.png
```

If uploaded, the app may still store them, but should show a warning that character matching may be unreliable.

### 4.4 Duplicate Character Names

The app must reject duplicate character reference names after extension removal.

Invalid example:

```text
Akira.png
Akira.jpg
```

Suggested user-facing error:

```text
Two character images use the same character name: Akira. Please keep only one reference image per character.
```

### 4.5 Filename Rename Support

Phase 1 does not need to implement in-app file renaming.

Simpler MVP behavior:

- Show validation error or warning.
- Ask the user to rename the file on their computer.
- Re-upload the corrected file.

---

## 5. Reference Image Quality Requirements

### 5.1 Recommended Reference Image

The ideal Phase 1 character reference image should be:

- Full-body.
- Front-facing or near-front-facing.
- Anime style.
- Clear face.
- Clear outfit.
- Single character only.
- No heavy occlusion.
- No extreme crop.
- No heavy motion blur.
- No complex background hiding the character.

### 5.2 Minimum Image Dimensions

Recommended minimum:

```text
512x512
```

Recommended better input:

```text
768x768 or higher
```

The app should warn, not necessarily reject, if the image is smaller than the recommendation.

### 5.3 Aspect Ratio

Accepted reference images may be portrait, square, or landscape, but full-body portrait images are recommended.

Recommended:

```text
Portrait or square image with the full character visible
```

### 5.4 Single Character Rule

A reference image should contain one character only.

If the image contains multiple characters, IP-Adapter-FaceID may pick the wrong face or produce unstable identity guidance.

Phase 1 can handle this as a warning rather than hard rejection if automatic face detection is not implemented yet.

Suggested user-facing warning:

```text
This image may contain more than one character. For better consistency, upload one full-body image with only this character.
```

---

## 6. Character Detection and Mapping

### 6.1 Story Character Candidates

After story upload, GPT scene splitting may detect character names from the story.

The app should compare detected story character names against uploaded character reference filenames.

Example detected characters:

```json
[
  "Akira",
  "Hana",
  "Yuki"
]
```

Uploaded character references:

```text
Akira.png
Hana.png
Yuki.png
```

Expected result:

```json
{
  "Akira": "input/characters/Akira.png",
  "Hana": "input/characters/Hana.png",
  "Yuki": "input/characters/Yuki.png"
}
```

### 6.2 Missing Reference Handling

If a detected main character has no matching image, the app should block final generation until the user resolves it.

Suggested user-facing error:

```text
Missing character reference for Akira. Please upload a full-body image named Akira.png.
```

### 6.3 Extra Reference Handling

If the user uploads a character image that is not detected in the story, do not fail automatically.

Show a warning:

```text
This character image was uploaded but was not detected in the story: Ren.png.
```

Possible reasons:

- The character appears under a different name.
- The character is not used in the current story.
- GPT failed to detect the character.
- The uploaded file is for a future scene.

### 6.4 Manual Override

Phase 1 may keep manual override out of scope.

Recommended MVP behavior:

- Use filename matching.
- Show clear missing/extra warnings.
- Let the user rename and re-upload files.

Manual mapping UI can be added later if filename matching becomes too limiting.

---

## 7. Storage Rules

### 7.1 Stored Folder

Character reference images must be stored locally under the project folder:

```text
projects/{project_id}/input/characters/
```

Example:

```text
projects/abc123/input/characters/Akira.png
projects/abc123/input/characters/Hana.png
```

### 7.2 Preserve Original Files

The app should preserve the uploaded reference image as the original source file.

Do not overwrite the original image during preprocessing.

### 7.3 Optional Processed Copies

If preprocessing is needed for IP-Adapter-FaceID or generation, save derived files separately.

Recommended folder:

```text
projects/{project_id}/metadata/character_cache/
```

This folder is part of the shared Phase 1 project folder structure and must also appear in PRD, user-flow, and future project-structure docs.

Example:

```text
projects/abc123/metadata/character_cache/Akira_face_crop.png
projects/abc123/metadata/character_cache/Akira_face_embedding.json
```

Do not require this cache structure if the first implementation can pass image paths directly to the generation pipeline.

### 7.4 Replacement Behavior

If the user replaces a character reference image before scene approval:

- Replace the stored file.
- Re-run validation.
- Mark character metadata as updated.
- Keep scene split data unless character names changed.

If the user replaces a character reference image after prompts or outputs already exist:

- Mark existing prompts and generated images as potentially stale.
- Require regeneration for affected scenes if the user wants consistency with the new reference.

Simpler Phase 1 behavior:

```text
Replacing a character image after generation does not modify existing outputs. New outputs use the new reference.
```

---

## 8. Character Metadata

### 8.1 Metadata File

Character reference metadata should be saved to:

```text
projects/{project_id}/metadata/characters.json
```

### 8.2 Recommended JSON Shape

```json
{
  "version": 1,
  "characters": [
    {
      "name": "Akira",
      "original_filename": "Akira.png",
      "stored_path": "input/characters/Akira.png",
      "mime_type": "image/png",
      "width": 1024,
      "height": 1536,
      "file_size_bytes": 842120,
      "is_full_body_expected": true,
      "consistency_method": "ip_adapter_faceid",
      "status": "valid",
      "warnings": []
    }
  ]
}
```

### 8.3 Status Values

Allowed character reference status values:

```text
valid
warning
invalid
missing
```

Meaning:

- `valid`: Reference is usable.
- `warning`: Reference is usable, but quality may hurt consistency.
- `invalid`: Reference cannot be used.
- `missing`: Character was detected in the story but no matching reference exists.

### 8.4 Warning Codes

Recommended warning codes:

```text
LOW_RESOLUTION
NOT_FULL_BODY_CONFIRMED
MULTIPLE_CHARACTERS_POSSIBLE
FACE_NOT_CLEAR
FILENAME_MISMATCH_POSSIBLE
EXTRA_REFERENCE_NOT_IN_STORY
NON_PREFERRED_FORMAT
```

### 8.5 Error Codes

Recommended error codes:

```text
UNSUPPORTED_CHARACTER_IMAGE_TYPE
CORRUPT_CHARACTER_IMAGE
DUPLICATE_CHARACTER_NAME
MISSING_CHARACTER_REFERENCE
INVALID_CHARACTER_FILENAME
CHARACTER_IMAGE_TOO_LARGE
CHARACTER_IMAGE_EMPTY
```

---

## 9. IP-Adapter-FaceID Requirements

### 9.1 Selected Approach

All Phase 1 documentation that touches character consistency should use:

```text
IP-Adapter-FaceID
```

This is the chosen character consistency direction for the app.

### 9.2 Role in the Pipeline

IP-Adapter-FaceID should be used to guide character identity during image generation based on the uploaded character reference image.

The generation pipeline should combine:

- Scene prompt.
- Character prompt traits.
- Uploaded character reference image.
- IP-Adapter-FaceID identity guidance.
- Diffusers image generation pipeline.

### 9.3 Identity Scope

IP-Adapter-FaceID is primarily identity guidance, especially around face consistency.

Outfit and body consistency still require prompt support.

Therefore each scene prompt should still include concise character descriptors such as:

```text
Akira, black messy hair, blue school jacket, slim teenage boy, same outfit as reference
```

Do not rely on IP-Adapter-FaceID alone to preserve every visual detail.

### 9.4 Multiple Characters in One Scene

When a scene contains multiple main characters, the generation pipeline must pass the relevant references for each character if the chosen implementation supports multi-character conditioning.

If the first implementation cannot reliably condition multiple characters at once, the app should document the limitation clearly and prefer safer prompt construction.

Possible MVP limitation:

```text
Multi-character scenes are supported best-effort and may have weaker identity consistency than single-character scenes.
```

### 9.5 Fallback Behavior

If IP-Adapter-FaceID dependencies are unavailable, fail, or the app detects low-VRAM mode:

- Do not silently generate without telling the user.
- Show a clear error or warning.
- On 4GB VRAM machines, disable IP-Adapter-FaceID by default and use prompt-based character hints unless the user explicitly opts into an advanced unsupported mode.
- Prevent generation only when the project requires character consistency and no fallback has been accepted.

Suggested user-facing error:

```text
Character consistency setup failed. Please check the local IP-Adapter-FaceID installation before generating character scenes.
```

### 9.6 Do Not Add LoRA Training in Phase 1

Advanced character LoRA training is out of scope for Phase 1.

Do not implement:

- Per-character LoRA training.
- DreamBooth fine-tuning.
- Dataset preparation workflows.
- Long-running character training jobs.

---

## 10. Prompt Integration Rules

### 10.1 Character Prompt Snippets

For each valid character reference, the app should maintain a short character prompt snippet.

Example:

```json
{
  "name": "Akira",
  "prompt_snippet": "Akira, teenage boy, black messy hair, blue school jacket, slim build, anime style, same outfit as reference"
}
```

Phase 1 snippet source rule:

- The app must not pretend it can extract detailed visual traits from the reference image unless a separate image-captioning or vision step is explicitly implemented later.
- Without image-captioning, the default snippet should be conservative and based on the canonical character name, same-outfit reminder, and optional user-provided description if such a field is added.
- GPT-extracted story context may only add non-visual story context such as role, age category if explicitly stated, relationship, or mood. It must not invent hair color, clothing, body type, or facial details.
- If no reliable visual description exists, use a safe minimal snippet such as: `Akira, same outfit and visual identity as the uploaded reference image, anime style`.
- Detailed visual snippets can be improved later through optional UI fields or a dedicated reference-image captioning step.

### 10.2 Do Not Force Prompt Engineering on User

The user should not need to write advanced prompts like:

```text
face embeddings, adapter strength, identity conditioning, CFG scale, denoise ratio
```

These settings may exist internally or under advanced settings later, but the default UX must remain simple.

### 10.3 Scene-Level Character List

Each scene should include a list of characters present.

Example:

```json
{
  "scene_number": 1,
  "characters": ["Akira", "Hana"]
}
```

The prompt generation step uses this list to attach the correct character references.

---

## 11. UI Requirements

### 11.1 Character Upload Screen

The character upload screen should show:

- Upload area for character images.
- Current uploaded character list.
- Filename-based character name.
- Validation status.
- Warnings.
- Missing references after story analysis.
- Extra references not detected in story.

### 11.2 Recommended UI Copy

For upload instructions:

```text
Upload one full-body image for each main character. Name each file exactly like the character name in your story, for example Akira.png.
```

For consistency expectation:

```text
Character consistency helps the app keep faces and visual identity closer to your uploaded references. Results are best-effort and may vary by pose, scene, and model.
```

Do not expose the technical name `IP-Adapter-FaceID` in the default user-facing flow. It may appear in developer docs, logs, or advanced settings only.

For same outfit assumption:

```text
For Phase 1, each character is expected to wear the same outfit across the story.
```

### 11.3 Validation Feedback

The UI should not show only technical error codes.

Bad:

```text
MISSING_CHARACTER_REFERENCE
```

Good:

```text
Missing character reference for Hana. Upload a full-body image named Hana.png.
```

---

## 12. API / Backend Behavior

This section defines expected backend behavior. Exact endpoint design is specified later in `docs/08-api-spec.md`.

### 12.1 Upload Character Reference

Expected behavior:

1. Receive image upload for a project.
2. Validate file extension.
3. Decode image.
4. Extract dimensions and file size.
5. Derive character name from filename.
6. Reject duplicates.
7. Store original file under `input/characters/`.
8. Update `metadata/characters.json`.
9. Return validation result to UI.

### 12.2 Validate Against Story Characters

Expected behavior after scene splitting or character extraction:

1. Load detected characters.
2. Load uploaded character references.
3. Match by character name.
4. Mark missing references.
5. Mark extra references.
6. Block final generation if required main character references are missing.

### 12.3 Delete Character Reference

If deletion is implemented in Phase 1:

1. Remove reference image from `input/characters/`.
2. Remove or mark metadata entry.
3. Re-run character reference validation.
4. Mark affected scenes/prompts as stale if needed.

---

## 13. Generation Readiness Rules

Before image generation starts, the app must check:

- Story file exists and is valid.
- Scene list exists.
- Scene list has been approved by the user.
- Required character references exist.
- Character references are valid or accepted with warnings.
- IP-Adapter-FaceID setup is available if character scenes require consistency.
- Output folder is writable.

Generation must be blocked if:

- A required main character reference is missing.
- A character reference is corrupt or invalid.
- Duplicate character names exist.
- Scene list has not been approved.
- IP-Adapter-FaceID is required but unavailable.

---

## 14. Non-Goals

Do not implement these in Phase 1:

- Character LoRA training.
- DreamBooth training.
- Multiple outfits per character.
- Per-scene character costume changes.
- Complex character relationship database.
- Cloud character reference storage.
- Account-level character library.
- Face swap workflows.
- Guaranteed perfect identity preservation.
- Manual ComfyUI graph editing.
- Advanced adapter strength tuning in the default UI.

---

## 15. Acceptance Criteria

### 15.1 Upload Validation

- User can upload `.png`, `.jpg`, `.jpeg`, and `.webp` character references.
- Corrupt image files are rejected.
- Duplicate character names are rejected.
- Uploaded references are stored under `projects/{project_id}/input/characters/`.
- `metadata/characters.json` is updated after upload.

### 15.2 Filename Matching

- Character name is derived from filename without extension.
- Missing story character references are detected.
- Extra uploaded references are shown as warnings, not hard failures.
- Generation is blocked if required main character references are missing.

### 15.3 Consistency Method

- Character consistency sections use IP-Adapter-FaceID as the selected approach.
- The app wording uses best-effort consistency language.
- The app does not promise perfect face preservation.
- The app does not implement LoRA training in Phase 1.

### 15.4 User Experience

- Non-technical users can understand what to upload.
- Errors explain how to fix the issue.
- Advanced model terms are not exposed in the default flow unless necessary.
- Character validation happens before generation starts.

---

## 16. Example End-to-End Character Flow

```text
1. User uploads story.md.
2. GPT detects characters: Akira, Hana, Yuki.
3. User uploads Akira.png, Hana.png, Yuki.png.
4. App validates each image.
5. App maps filenames to character names.
6. App stores references in input/characters/.
7. App writes metadata/characters.json.
8. User reviews scenes.
9. User approves scenes.
10. Prompt generation attaches scene character names.
11. Generation pipeline loads matching reference images.
12. IP-Adapter-FaceID guides character identity.
13. Diffusers generates ordered anime images.
14. Outputs are saved with numeric scene prefixes.
```

---

## 17. Example Error Messages

### Missing Reference

```text
Missing character reference for Akira. Please upload a full-body image named Akira.png.
```

### Duplicate Character

```text
Two uploaded files map to the same character name: Akira. Please keep only one image for each character.
```

### Invalid File Type

```text
This file type is not supported for character references. Please upload a PNG, JPG, JPEG, or WEBP image.
```

### Corrupt Image

```text
This image could not be read. Please upload a different character reference image.
```

### Low Resolution Warning

```text
This image is smaller than recommended. It may reduce character consistency quality.
```

### IP-Adapter-FaceID Setup Error

```text
Character consistency setup failed. Please check the local IP-Adapter-FaceID installation before generating character scenes.
```

---

## 18. Notes for Later Documents

The following documents must build on this spec:

- `docs/05-scene-splitting-and-prompting-spec.md`
- `docs/06-techstack.md`
- `docs/07-architecture.md`
- `docs/08-api-spec.md`
- `docs/09-generation-pipeline.md`
- `docs/10-data-storage-spec.md`
- `AGENTS.md`
- `.codex/skills/skill-diffusers-image-generation.md`

Any future document that mentions character consistency should use IP-Adapter-FaceID as the selected approach unless the product decision changes.
