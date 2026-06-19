# Local AI Anime Storyboard Generator — Story Input Specification

**Document:** `docs/03-story-input-spec.md`  
**Product name:** Local AI Anime Storyboard Generator  
**Phase:** Phase 1 MVP  
**Status:** Draft based on confirmed product decisions  
**Primary user:** Non-technical anime/story creator  

---

## 1. Purpose

This document defines how the app accepts, validates, stores, reads, and prepares the user's story input for scene splitting and prompt generation.

The core product decision is that the user uploads a **free-form Markdown story file**. The user must not be required to write strict scene tags, JSON, YAML, screenplay formatting, or prompt-engineering syntax.

Expected creator experience:

```text
Upload story.md → app reads story → GPT splits story into scenes → user reviews scenes → generation starts only after approval
```

This document is the source of truth for:

- Accepted story file format.
- File validation rules.
- Markdown parsing expectations.
- Story normalization rules.
- Character name extraction support.
- Scene splitting handoff requirements.
- Error handling for story upload and parsing.
- Metadata saved from the story input step.

---

## 2. Product Rules

### 2.1 Free-Form Markdown Is Required

The app must accept free-form `.md` story files.

The user may write the story as:

- Plain prose.
- Dialogue-heavy text.
- Chapter-like Markdown.
- Rough notes.
- Short story format.
- Mixed narration and dialogue.

The app must not require the user to manually define scenes.

Do not require formats like:

```text
[SCENE 1]
[CHARACTER: Akira]
[LOCATION: Classroom]
[PROMPT: ...]
```

Those formats may be tolerated if the user naturally writes them, but they must never be mandatory.

### 2.2 Scene Splitting Is Automatic

The app uses GPT to understand the story and split it into ordered scenes.

The story input layer only prepares the story. It does not decide final scene boundaries by itself unless a later fallback mode is explicitly added.

### 2.3 Scene Review Is Mandatory

After GPT splits the story into scenes, the user must review and approve the scene list before image generation starts.

The app must not auto-generate images immediately after story upload.

### 2.4 Input Must Preserve Story Order

The original story order must be preserved during:

- File storage.
- Text extraction.
- Scene splitting handoff.
- Scene ordering.
- Output filename generation.

No sorting, grouping, or automatic reordering should happen before the user review step.

---

## 3. Supported File Type

### 3.1 Accepted Extension

Phase 1 accepts:

```text
.md
```

Only Markdown files are in scope for Phase 1.

### 3.2 Explicitly Unsupported in Phase 1

Do not support these as primary story input formats in Phase 1:

```text
.docx
.pdf
.txt
.rtf
.html
.json
.yaml
.csv
```

These may be added later, but Codex Agent must not implement them unless the product decision changes.

### 3.3 MIME Type Handling

Because local browsers and operating systems may report Markdown files differently, validation should not rely only on MIME type.

Recommended validation order:

1. Check file extension is `.md`.
2. Try to read file as UTF-8 text.
3. Reject binary-looking content.
4. Save the file only after validation passes.

Acceptable MIME types may include:

```text
text/markdown
text/plain
application/octet-stream
```

`application/octet-stream` should be allowed only if the extension is `.md` and the content can be decoded safely as text.

---

## 4. File Naming Rules

### 4.1 User Upload Name

The user may upload any `.md` filename.

Examples:

```text
story.md
akira_episode_1.md
chapter-one.md
my anime idea.md
```

### 4.2 Stored Filename

After upload, the app stores the file as:

```text
projects/{project_id}/input/story.md
```

The original filename should be saved in project metadata.

Example metadata:

```json
{
  "original_story_filename": "akira_episode_1.md",
  "stored_story_path": "input/story.md"
}
```

### 4.3 Replacement Behavior

If the user uploads a new story file before scene approval:

- Replace `input/story.md`.
- Re-run story validation.
- Mark previous scene split result as stale.
- Require scene splitting again.

If the user uploads a new story file after scenes were approved:

- Require explicit confirmation in the UI.
- Clear or archive existing `scenes.json` and `prompts.json`.
- Mark generated outputs as no longer matching current input.

Phase 1 can implement the safer version:

```text
Changing story after approval resets the scene list and requires approval again.
```

---

## 5. Encoding Rules

### 5.1 Required Encoding

The app should read uploaded `.md` files as:

```text
UTF-8
```

### 5.2 UTF-8 BOM

UTF-8 with BOM should be accepted.

The BOM should be removed from the normalized story text before saving metadata.

### 5.3 Unsupported Encodings

If the file cannot be decoded as UTF-8, show a clear error.

Suggested user-facing error:

```text
This story file could not be read as UTF-8 text. Please save it as a UTF-8 .md file and upload again.
```

---

## 6. Size Limits

### 6.1 MVP Limits

Recommended Phase 1 limits:

| Limit | Value | Reason |
|---|---:|---|
| Minimum file size | 1 character after trimming | Prevent empty upload. |
| Maximum file size | 1 MB | Enough for long stories while keeping parsing simple. |
| Maximum normalized characters | 120,000 characters | Helps avoid excessive GPT input size. |
| Warning threshold | 60,000 characters | Tell user splitting may take longer or need chunking later. |

### 6.2 Empty File Handling

Reject files with no meaningful content after trimming whitespace.

Suggested user-facing error:

```text
Your story file is empty. Please add story text and upload again.
```

### 6.3 Very Large Story Handling

For Phase 1, reject files above the hard limit instead of implementing complex multi-part story processing.

Suggested user-facing error:

```text
This story file is too large for Phase 1. Please upload a shorter .md file under 1 MB.
```

A later version may support chapter-level chunking.

---

## 7. Markdown Content Rules

### 7.1 Allowed Markdown Elements

The app should tolerate common Markdown syntax:

- Headings.
- Paragraphs.
- Bullet lists.
- Numbered lists.
- Blockquotes.
- Italic and bold text.
- Horizontal rules.
- Inline code.
- Fenced code blocks.

The app does not need to render all Markdown perfectly during parsing. The priority is extracting readable story text.

### 7.2 Markdown Headings

Headings may help GPT understand structure.

Examples:

```markdown
# Episode 1: The Transfer Student

## Morning

## After School
```

The app should preserve heading text in the normalized story text sent to GPT.

### 7.3 Dialogue

The app should support dialogue written in multiple common styles.

Examples:

```markdown
Akira: I heard something in the hallway.

Hana said, "Don't open that door."

"Wait for me," Yuki whispered.
```

The app should not require a strict dialogue format.

### 7.4 Images Inside Markdown

Markdown image references are not part of Phase 1 story input.

If the story contains:

```markdown
![Akira](./akira.png)
```

The app may keep the alt text as plain text, but it must not treat embedded Markdown images as character references.

Character references must be uploaded separately through the character upload flow.

### 7.5 Links Inside Markdown

Links may be kept as plain text or stripped to visible text.

Recommended normalization:

```markdown
[school rooftop](https://example.com)
```

Becomes:

```text
school rooftop
```

The app should not fetch remote URLs.

### 7.6 HTML Inside Markdown

Raw HTML should not be executed.

For parsing, the app should treat raw HTML as text or strip tags safely.

Never render unsanitized story HTML in the UI.

---

## 8. Story Text Normalization

### 8.1 Goals

Normalization should make the story safer and easier to process while preserving meaning and order.

### 8.2 Normalization Steps

Recommended steps:

1. Decode as UTF-8.
2. Remove UTF-8 BOM if present.
3. Normalize line endings to `\n`.
4. Trim leading and trailing whitespace.
5. Collapse excessive blank lines only when they are clearly accidental.
6. Preserve headings, dialogue, paragraph order, and list order.
7. Remove null bytes and control characters that are not useful text.
8. Save normalized text metadata.

### 8.3 Do Not Over-Normalize

Do not rewrite the user's story aggressively.

Avoid:

- Reordering paragraphs.
- Translating the story.
- Summarizing the story before GPT scene splitting.
- Removing character names.
- Removing dialogue markers.
- Removing headings that help structure.

---

## 9. Language Handling

### 9.1 Supported Story Languages

Phase 1 should support at least:

- English.
- Vietnamese.

The app should not hard-code English-only parsing assumptions.

### 9.2 Language Detection

The app may ask GPT to detect the story language during scene splitting.

The input spec does not require a local language detection library in Phase 1.

### 9.3 Prompt Output Language

Prompt generation may output English prompts for better image model behavior, even if the story is Vietnamese.

However, user-facing scene summaries should preserve the user's understandable language when possible.

Detailed rules belong in `docs/05-scene-splitting-and-prompting-spec.md`.

---

## 10. Character Name Extraction Support

### 10.1 Purpose

The story input flow should help the later character validation step by preserving text that may contain character names.

The app should not require users to declare character names inside a structured story header.

### 10.2 Optional Character Hints

The user may optionally include character hints in the story, but they are not required.

Example allowed but not mandatory:

```markdown
Characters:
- Akira
- Hana
- Yuki
```

If present, GPT can use this section to identify main characters.

### 10.3 Filename Matching Rule

The character reference spec remains the source of truth for image matching, but the story input must preserve character names exactly enough for matching.

Matching rule:

- Character matching is case-insensitive for validation convenience.
- The stored canonical character name preserves the uploaded filename stem casing.
- If the story says `akira` and the uploaded file is `Akira.png`, the app may match them but should warn the user that casing differs and recommend consistent naming.

Example:

If the story contains:

```text
Akira
```

The expected character file is:

```text
Akira.png
```

### 10.4 Character Consistency Note

When a detected character is later used in image generation, the chosen Phase 1 character consistency approach is **IP-Adapter-FaceID**.

Story input does not run IP-Adapter-FaceID directly. It only helps produce accurate scene metadata so the generation pipeline knows which character references are needed per scene.

---

## 11. Upload Flow

### 11.1 UI Flow

Story upload screen should show:

- Upload area for `.md` file.
- Clear text explaining that free-form story is accepted.
- File validation status.
- Preview of uploaded story content.
- Button to continue to character upload or scene splitting.

Suggested UI copy:

```text
Upload your story as a Markdown file. You do not need to write scene tags — the app will split the story into scenes for you.
```

### 11.2 Backend Flow

Recommended backend steps:

```text
1. Receive uploaded file.
2. Validate extension is .md.
3. Read bytes.
4. Decode as UTF-8.
5. Normalize story text.
6. Validate non-empty content.
7. Validate size limits.
8. Save original uploaded file as input/story.md.
9. Save story metadata.
10. Mark project story status as uploaded.
```

### 11.3 Story Upload Status Values

Recommended statuses:

```text
NOT_UPLOADED
UPLOADED
VALIDATION_FAILED
STALE_AFTER_REUPLOAD
```

These may be stored in `project.json` or equivalent local metadata.

---

## 12. Story Preview Requirements

### 12.1 Preview Purpose

The preview helps the user confirm they uploaded the correct file.

### 12.2 Preview Content

The UI should show:

- Original filename.
- File size.
- Character count.
- Approximate word count.
- First part of story text.

Recommended preview limit:

```text
First 2,000 characters
```

### 12.3 Full Story View

Phase 1 may include a simple full story view, but it is not required.

If implemented, sanitize rendered Markdown to avoid unsafe HTML execution.

---

## 13. Scene Splitting Handoff

### 13.1 Handoff Trigger

Scene splitting can run after:

1. Story file is uploaded and valid.
2. Character files are uploaded or the app has enough information to proceed.

Recommended Phase 1 UX:

```text
Upload story → upload character images → validate filenames → split scenes
```

This allows GPT to use the known character names when splitting scenes.

### 13.2 Data Sent to Scene Splitting Service

The scene splitting service should receive:

```json
{
  "project_id": "project_uuid_or_slug",
  "story": {
    "original_filename": "akira_episode_1.md",
    "normalized_text": "...",
    "character_count": 24500,
    "language_hint": null
  },
  "characters": [
    {
      "name": "Akira",
      "reference_filename": "Akira.png"
    },
    {
      "name": "Hana",
      "reference_filename": "Hana.png"
    }
  ],
  "output_preset": {
    "name": "YouTube Standard",
    "width": 1280,
    "height": 720,
    "aspect_ratio": "16:9"
  }
}
```

### 13.3 Required Handoff Guarantees

The story input layer must guarantee:

- `normalized_text` is valid UTF-8 text.
- Text order matches the uploaded story.
- File passed extension validation.
- Empty files are rejected.
- Size limits are enforced.
- Metadata is saved before scene splitting.

---

## 14. Metadata Output

### 14.1 Story Metadata File

Recommended file:

```text
projects/{project_id}/metadata/story.json
```

This file is part of the shared Phase 1 project folder structure and must be listed alongside the other metadata files in PRD, user-flow, and future project-structure docs.



### 14.1.1 Folder Structure Alignment

The story input step contributes `metadata/story.json` to the shared project folder structure:

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

`metadata/character_cache/` is owned by the character/generation pipeline, but it is included here so every document uses the same master structure.

### 14.2 Example Metadata

```json
{
  "story_status": "UPLOADED",
  "original_filename": "akira_episode_1.md",
  "stored_path": "input/story.md",
  "file_size_bytes": 42811,
  "character_count": 38120,
  "approx_word_count": 7100,
  "line_count": 890,
  "encoding": "utf-8",
  "uploaded_at": "2026-06-10T12:00:00Z",
  "content_hash": "sha256:...",
  "normalized_line_endings": true
}
```

### 14.3 Content Hash

The app should compute a SHA-256 hash of the normalized story text.

Purpose:

- Detect whether scene outputs are stale.
- Know whether story content changed after scene splitting.
- Avoid confusing old scenes with new story input.

---

## 15. Staleness Rules

### 15.1 Scene List Staleness

`scenes.json` becomes stale when:

- `story.json.content_hash` changes.
- Character references change in a way that affects detected character names.
- Output preset changes in a way that affects prompt framing.

### 15.2 Prompt Staleness

`prompts.json` becomes stale when:

- Approved scene text changes.
- Character references change.
- Output preset changes.
- Generation style settings change.

### 15.3 Generated Output Staleness

Generated images are considered stale when:

- Story content changes after generation.
- Scene order changes after generation.
- Scene text changes after generation.
- Character reference images change after generation.

Phase 1 should not silently delete stale outputs. It should mark them as stale or create a new generation run folder if generation history is implemented.

---

## 16. Validation Errors

### 16.1 Error Codes

Recommended backend error codes:

| Code | Meaning |
|---|---|
| `STORY_FILE_REQUIRED` | No story file was uploaded. |
| `STORY_UNSUPPORTED_FILE_TYPE` | File extension is not `.md`. |
| `STORY_INVALID_ENCODING` | File cannot be decoded as UTF-8. |
| `STORY_EMPTY` | File has no meaningful text. |
| `STORY_TOO_LARGE` | File exceeds Phase 1 size limit. |
| `STORY_BINARY_CONTENT_DETECTED` | File looks like binary data. |
| `STORY_SAVE_FAILED` | App could not save file locally. |
| `STORY_READ_FAILED` | App could not read stored story file. |

### 16.2 Error Response Shape

Recommended API-style response:

```json
{
  "error": {
    "code": "STORY_UNSUPPORTED_FILE_TYPE",
    "message": "Please upload a Markdown .md story file.",
    "details": {
      "received_filename": "story.pdf"
    }
  }
}
```

For HTMX UI, the backend may render an error partial using the same code and message.

---

## 17. Security and Safety

### 17.1 Local File Safety

The app must not trust uploaded filenames as paths.

Reject or sanitize:

```text
../story.md
C:\Users\name\secret.md
folder/story.md
```

The stored path is always controlled by the app:

```text
input/story.md
```

### 17.2 No Remote Fetching

The app must not fetch links found in the Markdown story.

### 17.3 No HTML Execution

If the story preview renders Markdown, sanitize HTML.

Do not execute scripts from story content.

### 17.4 Local-First Privacy

The story is stored locally.

However, Phase 1 uses the OpenAI API for story understanding and scene splitting, so the story text may be sent to OpenAI when the user runs scene splitting.

The UI should make this clear before the scene splitting step.

Suggested UI copy:

```text
Scene splitting uses the OpenAI API. Your story text will be sent for scene analysis and prompt generation.
```

---

## 18. Implementation Guidance

### 18.1 Suggested Python Utilities

Implementation may use standard Python libraries:

```text
pathlib
hashlib
datetime
re
unicodedata
```

Markdown parsing does not need a complex dependency for Phase 1 unless the UI needs rendered Markdown preview.

### 18.2 Recommended Internal Functions

```python
def validate_story_upload(filename: str, content: bytes) -> StoryValidationResult:
    ...


def normalize_story_text(raw_text: str) -> str:
    ...


def compute_story_hash(normalized_text: str) -> str:
    ...


def save_story_file(project_id: str, normalized_text: str) -> Path:
    ...


def write_story_metadata(project_id: str, metadata: StoryMetadata) -> None:
    ...
```

These names are illustrative. Final code may choose different names if it keeps the same behavior.

### 18.3 Do Not Implement Here

This document does not define:

- Final scene splitting prompt.
- Full OpenAI API request/response schema.
- Character image validation details.
- IP-Adapter-FaceID runtime implementation.
- Diffusers generation settings.
- Final API endpoint list.

Those belong in later docs.

---

## 19. Acceptance Criteria

A Phase 1 implementation satisfies this spec when:

1. The user can upload a `.md` story file.
2. The app rejects unsupported file extensions.
3. The app rejects empty files.
4. The app rejects files that cannot be decoded as UTF-8.
5. The app stores the story as `projects/{project_id}/input/story.md`.
6. The app saves story metadata including original filename, stored path, file size, character count, and content hash.
7. The app preserves story order and text meaning during normalization.
8. The app can show a story preview after upload.
9. The app marks previous scene data stale when the story changes.
10. The app does not require structured scene tags.
11. The app does not start image generation directly after story upload.
12. The app can pass normalized story text to the scene splitting service.
13. The app does not fetch remote URLs from story Markdown.
14. The app sanitizes story preview rendering if Markdown is rendered as HTML.

---

## 20. Out of Scope

The following are out of scope for this document and Phase 1 story input unless explicitly added later:

- PDF story parsing.
- DOCX story parsing.
- Audio transcription.
- Voice script import.
- Subtitle file import.
- Automatic translation.
- Cloud story storage.
- Multi-user story library.
- Real-time collaborative editing.
- Full screenplay parser.
- Mandatory structured scene syntax.

---

## 21. Related Documents

- `docs/00-product-decisions.md`
- `docs/01-prd.md`
- `docs/02-user-flow.md`
- `docs/04-character-reference-spec.md`
- `docs/05-scene-splitting-and-prompting-spec.md`
- `docs/10-data-storage-spec.md`
- `docs/12-error-handling-logging.md`
