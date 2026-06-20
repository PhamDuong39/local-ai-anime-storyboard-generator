# Product Requirements Document (PRD) — VideoHUB

## 1. Document Overview

### 1.1 Product Name

**VideoHUB**

### 1.2 Product Type

VideoHUB is a public, multi-user video platform that allows guests to watch public videos without logging in, while registered users can upload, process, publish, and manage their own videos through a Creator Studio.

The product is conceptually similar to a minimal version of YouTube, but Phase 1 focuses only on the core media lifecycle:

```text
Upload video → Process video → Playback → Manage personal videos
```

### 1.3 Purpose of This Document

This PRD defines the product requirements, MVP scope, user roles, core user journeys, functional requirements, non-functional requirements, and long-term roadmap for VideoHUB.

This document intentionally includes both:

1. **MVP Phase 1 requirements**, which are the features to be built first.
2. **Long-term product direction**, which outlines future capabilities such as search, subscriptions, reporting, analytics, and platform-scale features.

The goal is to keep Phase 1 focused while ensuring the architecture is not short-sighted.

---

## 2. Product Vision

### 2.1 Vision Statement

VideoHUB aims to be a creator-first video platform where users can upload, process, publish, and share videos publicly through a reliable self-hosted media infrastructure.

The first version should validate the core technical foundation of a video platform:

- Reliable upload of large video files.
- Asynchronous video processing.
- HLS-based playback.
- Creator-owned video management.
- Public viewing without authentication.
- Identity and access control using Keycloak.
- Cost-optimized self-hosted infrastructure using MinIO and FFmpeg.

### 2.2 Product Goals

The key goals of VideoHUB are:

1. Provide a working public video platform with core upload and playback capabilities.
2. Allow creators to manage their own videos in a private Studio area.
3. Support large video uploads through chunked upload, retry, and resume mechanisms.
4. Process uploaded videos asynchronously into playback-ready HLS assets.
5. Store original and processed media using self-hosted MinIO object storage.
6. Use Keycloak as the central Identity Provider with support for Google SSO.
7. Establish a clean event-driven foundation using Kafka for future analytics, search indexing, notifications, activity logs, and moderation workflows.

### 2.3 Product Non-goals for Phase 1

The following features are intentionally excluded from Phase 1 implementation:

- Likes.
- Comments.
- Subscribe/follow creator.
- Playlists.
- Full-text video search.
- Recommendation system.
- Advanced analytics dashboard.
- Report content workflow.
- Manual content moderation dashboard.
- Monetization.
- Live streaming.
- Real-time chat.
- Video ads.
- Organization/team-based tenant management.

However, the architecture and PRD should still reserve space for these features in later phases.

---

## 3. Target Users

### 3.1 Guest Viewer

A guest viewer is an unauthenticated user who can access public videos through the Viewing Site.

Guest viewers can:

- Open public video pages.
- Watch videos that are ready and publicly visible.
- View basic video metadata such as title, description, creator handle, thumbnail, and publish date.

Guest viewers cannot:

- Upload videos.
- Manage videos.
- View private videos.
- Access Creator Studio.
- Comment, like, subscribe, or report content in Phase 1.

### 3.2 Registered Creator

A registered creator is an authenticated user who can upload and manage their own videos.

Creators can:

- Log in through Keycloak.
- Upload videos through Creator Studio.
- Resume failed or interrupted uploads.
- View upload and processing status.
- Manage their own video metadata.
- Set video visibility as `PUBLIC` or `PRIVATE`.
- View their own videos even when videos are still processing, failed, private, or hidden by moderation.

Creators cannot:

- Manage other creators' videos.
- Override moderation decisions.
- Change a hidden video back to public.
- Access admin-only moderation tools.

### 3.3 Admin / Moderator

Admin and moderator capabilities are not part of Phase 1 implementation, but the system must reserve the data model and rules for future moderation.

Admins or moderators will eventually be able to:

- Hide videos that violate platform rules.
- Review reported videos.
- Lock videos permanently through `moderation_status = HIDDEN`.
- Audit moderation actions.

For Phase 1, moderation behavior may be represented at the data model and service rule level, even if the full admin UI is deferred.

---

## 4. Product Scope

## 4.1 MVP Phase 1 Scope

Phase 1 focuses on the smallest complete video platform loop:

```text
Creator signs in
→ Creator uploads video using chunked upload
→ Backend stores chunks in temporary MinIO bucket
→ System verifies all chunks
→ System merges chunks into original video object
→ Backend creates video record
→ Kafka event triggers media processing
→ Media Worker transcodes video using FFmpeg
→ Processed HLS outputs and thumbnail are stored in MinIO
→ Video status becomes READY
→ Public users can watch the video if visibility is PUBLIC and moderation is NORMAL
→ Creator can manage the video in Studio
```

### 4.1.1 Phase 1 Feature List

Phase 1 includes:

1. Public Viewing Site.
2. Creator Studio.
3. Keycloak-based authentication.
4. Google SSO through Keycloak configuration.
5. Creator profile/handle model.
6. Chunked upload.
7. Retry upload.
8. Resume upload.
9. Upload session tracking.
10. Temporary chunk storage in MinIO.
11. Server-side chunk verification.
12. Server-triggered merge/finalization.
13. Original video storage in MinIO.
14. Kafka-based asynchronous processing event.
15. FFmpeg-based Media Worker.
16. Metadata extraction.
17. Thumbnail generation.
18. HLS transcoding.
19. Video status tracking.
20. Video visibility control.
21. Basic playback page.
22. Creator video management page.
23. Basic authorization rules.
24. Basic moderation state support through `moderation_status`.

---

## 5. Multi-tenancy Strategy

### 5.1 Multi-tenancy Model

VideoHUB follows a **multi-user creator platform** model rather than an enterprise workspace model.

In Phase 1, the tenant-like boundary is the individual creator.

Each video belongs to exactly one creator.

The system uses:

```text
Shared Database + Shared Schema
```

Data isolation is enforced through:

```text
creator_id / user_id
```

### 5.2 Rationale

This model is selected because:

- The product targets individual creators first.
- It is simpler and cheaper to operate.
- It avoids premature enterprise-grade tenant isolation.
- It is similar to how creator-first platforms organize user-generated content.
- It supports future migration to organization/team models if needed.

### 5.3 URL Design

Public video pages follow this format:

```text
https://videohub.com/@creator/video-id
```

Example:

```text
https://videohub.com/@john/video-123
```

The `@creator` segment represents the creator handle.

The `video-id` identifies the video resource.

### 5.4 Tenant Isolation Rules

The system must enforce:

1. A creator can only manage videos they own.
2. A creator cannot access upload sessions owned by another creator.
3. A guest can only view videos that satisfy public playback rules.
4. Public playback must never expose private or hidden videos.
5. Admin-only moderation actions must not be available to regular creators.

---

## 6. Authentication and Authorization

### 6.1 Identity Provider

VideoHUB uses **Keycloak** as the independent Identity Provider.

Keycloak responsibilities:

- User authentication.
- User registration.
- Token issuance.
- Role management.
- Google SSO integration.
- Centralized identity lifecycle management.

### 6.2 Authentication Methods

Phase 1 should support:

1. Username/password login through Keycloak.
2. Google SSO configured through Keycloak.

### 6.3 Application Roles

Initial roles:

```text
GUEST
CREATOR
ADMIN
```

Role definitions:

| Role | Description |
|---|---|
| `GUEST` | Unauthenticated viewer. Can watch public videos only. |
| `CREATOR` | Authenticated user. Can upload and manage their own videos. |
| `ADMIN` | Platform-level role reserved for future moderation and operations. |

### 6.4 Authorization Rules

#### Public Viewing Rule

A video is publicly viewable only when:

```text
video.status == READY
AND video.visibility == PUBLIC
AND video.moderation_status == NORMAL
```

#### Creator Studio Rule

A creator can view their own videos in Studio regardless of:

```text
PROCESSING
READY
FAILED
PRIVATE
HIDDEN
```

However, if a video is hidden by moderation, the Creator Studio must show a warning and prevent the creator from making it public again.

#### Moderation Rule

Only an admin/system moderation actor can set:

```text
moderation_status = HIDDEN
```

Once a video becomes hidden, the creator cannot revert it to normal or public visibility.

---

## 7. Core Domain Concepts

## 7.1 Creator

A creator represents an authenticated user who can upload and manage videos.

Important fields:

```text
creator_id
keycloak_user_id
handle
display_name
avatar_url
created_at
updated_at
```

### 7.1.1 Creator Handle

The creator handle is used in public URLs:

```text
/@creator/video-id
```

Rules:

- Must be unique.
- Should be URL-safe.
- Should not conflict with reserved system paths.
- Should be change-controlled in later phases.

---

## 7.2 Video

A video represents a media asset uploaded by a creator.

Important fields:

```text
video_id
creator_id
title
description
status
visibility
moderation_status
original_object_key
hls_master_playlist_key
thumbnail_object_key
duration_seconds
width
height
size_bytes
created_at
updated_at
published_at
```

### 7.2.1 Video Status

`video.status` describes processing lifecycle state.

Allowed values:

```text
PROCESSING
READY
FAILED
```

Meaning:

| Status | Meaning |
|---|---|
| `PROCESSING` | Video has been uploaded and is being processed. |
| `READY` | Video has been successfully processed and can be played if visibility and moderation rules allow. |
| `FAILED` | Video processing failed. Creator can see the failure in Studio. |

### 7.2.2 Video Visibility

`video.visibility` describes creator-controlled visibility.

Allowed values:

```text
PUBLIC
PRIVATE
```

Meaning:

| Visibility | Meaning |
|---|---|
| `PUBLIC` | Video can be publicly viewed if status is READY and moderation is NORMAL. |
| `PRIVATE` | Video is visible only to the owning creator in Studio. |

### 7.2.3 Moderation Status

`video.moderation_status` describes platform-controlled moderation state.

Allowed values:

```text
NORMAL
HIDDEN
```

Meaning:

| Moderation Status | Meaning |
|---|---|
| `NORMAL` | Video has no moderation restriction. |
| `HIDDEN` | Video has been hidden by admin/system moderation and cannot be made public by the creator. |

---

## 7.3 Upload Session

An upload session tracks a chunked upload before it becomes a final video object.

Important fields:

```text
upload_session_id
creator_id
original_filename
mime_type
file_size_bytes
total_chunks
uploaded_chunks
chunk_size_bytes
status
checksum
temporary_bucket
temporary_prefix
final_object_key
created_at
updated_at
expires_at
completed_at
```

### 7.3.1 Upload Session Status

Allowed values:

```text
INITIATED
UPLOADING
MERGING
COMPLETED
FAILED
EXPIRED
```

Meaning:

| Status | Meaning |
|---|---|
| `INITIATED` | Upload session has been created but no chunks have been uploaded yet. |
| `UPLOADING` | At least one chunk has been uploaded. |
| `MERGING` | All chunks are present and the system is finalizing the original video object. |
| `COMPLETED` | Upload was successfully finalized. |
| `FAILED` | Upload failed and cannot proceed without retry or restart. |
| `EXPIRED` | Upload session expired and temporary chunks are eligible for cleanup. |

---

## 7.4 Media Asset

A media asset represents generated files related to a video.

Examples:

- Original uploaded file.
- HLS master playlist.
- HLS variant playlists.
- HLS media segments.
- Thumbnail image.
- Optional preview MP4.

Potential fields:

```text
asset_id
video_id
asset_type
quality
object_key
mime_type
size_bytes
created_at
```

Asset types may include:

```text
ORIGINAL
HLS_MASTER_PLAYLIST
HLS_VARIANT_PLAYLIST
HLS_SEGMENT
THUMBNAIL
PREVIEW_MP4
```

For Phase 1, media assets can either be modeled explicitly in a `media_asset` table or represented directly on the `video` record with key object references.

---

## 8. Core User Journeys

## 8.1 Guest Watches a Public Video

### Flow

1. Guest opens a URL such as:

```text
/@creator/video-id
```

2. Viewing Site requests video metadata from backend.
3. Backend checks public playback rule:

```text
status == READY
AND visibility == PUBLIC
AND moderation_status == NORMAL
```

4. If allowed, backend returns video metadata and playback manifest URL.
5. Frontend loads HLS player.
6. Player streams HLS content from MinIO or a media-serving layer.

### Success Criteria

- Guest can watch public ready videos without login.
- Guest cannot watch private videos.
- Guest cannot watch hidden videos.
- Guest cannot watch failed or processing videos.

---

## 8.2 Creator Uploads a Video

### Flow

1. Creator logs in through Keycloak.
2. Creator opens Creator Studio.
3. Creator selects a video file.
4. Frontend creates an upload session through backend.
5. Backend validates initial upload metadata.
6. Backend returns upload session information.
7. Frontend splits file into chunks.
8. Frontend uploads each chunk to backend.
9. Backend validates each chunk.
10. Backend stores each chunk directly into temporary MinIO bucket/prefix.
11. Backend tracks uploaded chunks in `upload_session`.
12. Frontend retries failed chunks if needed.
13. Frontend asks backend which chunks are missing when resuming upload.
14. Once all chunks are uploaded, frontend calls complete upload API.
15. Backend verifies all chunks exist.
16. Backend sets upload session status to `MERGING`.
17. Backend instructs MinIO/S3-compatible storage operation to compose or merge chunks into one original object.
18. Backend marks upload session as `COMPLETED`.
19. Backend creates a `video` record with `status = PROCESSING`.
20. Backend publishes a Kafka event to start media processing.

### Success Criteria

- Large files can be uploaded in chunks.
- Upload can recover from weak network conditions.
- Upload can resume by only sending missing chunks.
- Backend remains stateless and does not depend on local disk.
- Chunks are stored in MinIO temporary storage.
- Final original file is stored in MinIO.

---

## 8.3 System Processes an Uploaded Video

### Flow

1. Media Worker consumes Kafka event.
2. Worker loads video metadata and original object key.
3. Worker downloads or streams original file from MinIO.
4. Worker validates file type, duration, size, and media properties.
5. Worker extracts metadata.
6. Worker generates thumbnail.
7. Worker transcodes video into HLS outputs.
8. Worker stores processed outputs in MinIO.
9. Worker updates video metadata.
10. Worker sets video status to `READY` on success.
11. Worker sets video status to `FAILED` on failure.
12. Worker emits processing result event for future consumers.

### Success Criteria

- Video processing is asynchronous.
- API server does not run FFmpeg directly.
- Failed processing does not crash the platform.
- Retry strategy can be added around Kafka processing.
- HLS assets are generated consistently.

---

## 8.4 Creator Manages Videos in Studio

### Flow

1. Creator opens Creator Studio.
2. Frontend requests the creator's video list.
3. Backend returns only videos owned by that creator.
4. Creator can view status, visibility, thumbnail, title, and processing result.
5. Creator can edit title and description.
6. Creator can switch visibility between `PUBLIC` and `PRIVATE` if moderation status is `NORMAL`.
7. Creator cannot make a hidden video public.

### Success Criteria

- Creator sees all their own videos.
- Creator cannot see or manage other creators' videos.
- Processing and failed states are visible.
- Hidden videos are visible in Studio with a clear warning.

---

## 9. Functional Requirements

## 9.1 Public Viewing Site

### Requirements

The Viewing Site must:

1. Allow guests to open public video URLs.
2. Display video title.
3. Display video description.
4. Display creator handle/display name.
5. Display thumbnail before playback.
6. Load HLS playback source for eligible videos.
7. Return a not-found or unavailable page for private, processing, failed, or hidden videos.

### Public Playback Eligibility

A video is eligible for public playback only if:

```text
status = READY
visibility = PUBLIC
moderation_status = NORMAL
```

---

## 9.2 Creator Studio

### Requirements

Creator Studio must:

1. Require authentication.
2. Show the creator's own uploaded videos.
3. Show video processing status.
4. Allow upload of new videos.
5. Allow retry/resume of interrupted uploads.
6. Allow editing of video title and description.
7. Allow changing visibility between `PUBLIC` and `PRIVATE`.
8. Prevent public visibility when `moderation_status = HIDDEN`.
9. Show clear error states for failed upload or failed processing.

---

## 9.3 Upload Session Management

### Requirements

The backend must support:

1. Creating upload sessions.
2. Validating upload metadata.
3. Receiving chunks from client.
4. Validating chunk index, size, upload session ownership, and session status.
5. Storing chunks directly into temporary MinIO bucket/prefix.
6. Tracking uploaded chunks.
7. Listing missing chunks for resume.
8. Completing upload only when all chunks exist.
9. Triggering object merge/finalization.
10. Cleaning expired or completed temporary chunks asynchronously.

### Upload Constraints

Phase 1 should define practical constraints even if the product goal says “large upload support”.

Recommended constraints for MVP:

```text
Max file size: configurable
Allowed MIME types: video/mp4, video/quicktime, video/x-matroska, video/webm
Max duration: configurable
Chunk size: configurable
Upload session expiration: configurable
```

The actual values should be defined in the technical architecture document.

---

## 9.4 Media Processing

### Requirements

The Media Worker must:

1. Consume video processing jobs from Kafka.
2. Validate source media.
3. Extract metadata.
4. Generate thumbnail.
5. Transcode video into HLS.
6. Generate multiple quality variants where possible.
7. Store processed assets in MinIO.
8. Update video status and metadata.
9. Record failure reason on processing failure.
10. Emit result event after processing completion.

### Target HLS Variants

Phase 1 target variants:

```text
360p
720p
1080p
```

The system should generate only variants that make sense based on source video resolution.

Example:

- Source 480p → generate 360p only.
- Source 720p → generate 360p and 720p.
- Source 1080p or higher → generate 360p, 720p, and 1080p.

---

## 9.5 Video Management

### Requirements

Creators must be able to:

1. View their videos.
2. View processing status.
3. View upload/processing failure states.
4. Update title.
5. Update description.
6. Update visibility.
7. See whether a video is hidden by moderation.

Phase 1 may defer:

- Delete video.
- Bulk edit.
- Replace video file.
- Custom thumbnail upload.
- Scheduled publishing.

---

## 9.6 Moderation State Support

Phase 1 does not include a full reporting/moderation workflow, but the system must include moderation status in the video model.

### Requirements

1. `moderation_status` must default to `NORMAL`.
2. `HIDDEN` videos must not be publicly accessible.
3. Creator Studio must still show hidden videos to the owner.
4. Creators must not be able to change hidden videos back to public availability.
5. Admin/system actor must be reserved as the only actor that can set `HIDDEN`.

---

## 10. Storage Requirements

## 10.1 Object Storage

VideoHUB uses **MinIO** as self-hosted object storage.

MinIO stores:

- Temporary upload chunks.
- Original uploaded videos.
- Transcoded HLS outputs.
- Thumbnails.
- Future media derivatives.

### 10.2 Bucket Strategy

Recommended bucket structure:

```text
videohub-temp-uploads
videohub-originals
videohub-processed
videohub-thumbnails
```

Alternative: one bucket with strict prefixes.

Recommended object key structure:

```text
/temp-uploads/{upload_session_id}/chunks/{chunk_index}
/originals/{creator_id}/{video_id}/source
/processed/{creator_id}/{video_id}/hls/master.m3u8
/processed/{creator_id}/{video_id}/hls/360p/index.m3u8
/processed/{creator_id}/{video_id}/hls/720p/index.m3u8
/processed/{creator_id}/{video_id}/hls/1080p/index.m3u8
/thumbnails/{creator_id}/{video_id}/default.jpg
```

### 10.3 Storage Cleanup

The system must eventually clean:

1. Expired upload chunks.
2. Completed temporary chunks.
3. Failed upload session chunks.
4. Orphaned processed assets from failed jobs.

Phase 1 should include at least a scheduled cleanup job for temporary upload chunks.

---

## 11. Event-driven Architecture Requirements

## 11.1 Kafka Usage

VideoHUB uses Kafka as the message broker from Phase 1.

Kafka is used to support:

1. Media processing jobs.
2. Processing result events.
3. Future analytics events.
4. Future search indexing events.
5. Future activity logs.
6. Future moderation workflows.

### 11.2 Initial Kafka Topics

Recommended Phase 1 topics:

```text
video.upload.completed
video.processing.requested
video.processing.completed
video.processing.failed
```

Possible future topics:

```text
video.view.recorded
video.metadata.updated
video.visibility.changed
video.report.created
creator.subscribed
search.index.requested
activity.logged
```

### 11.3 Processing Reliability

The architecture should define:

- Consumer group for media workers.
- Retry policy.
- Dead-letter topic for failed jobs.
- Idempotent processing behavior.
- Safe handling of duplicate Kafka messages.

Media processing must be idempotent enough that re-consuming a processing event does not corrupt video state or duplicate assets incorrectly.

---

## 12. Playback Requirements

## 12.1 Playback Format

Public playback should primarily use **HLS**.

The HLS output should include:

```text
master.m3u8
variant playlists
media segments
```

### 12.2 Playback Access Rule

The backend must authorize playback metadata requests according to:

```text
status = READY
visibility = PUBLIC
moderation_status = NORMAL
```

### 12.3 Media Delivery

For Phase 1, media may be served from MinIO directly or through a backend/media gateway depending on the chosen infrastructure setup.

Long-term, the system should support CDN integration in front of processed media assets.

### 12.4 Future Playback Enhancements

Future phases may include:

- Signed playback URLs.
- Anti-hotlinking.
- Bandwidth throttling.
- CDN caching strategy.
- Adaptive bitrate tuning.
- DRM or token-based access control for private content.

---

## 13. Non-functional Requirements

## 13.1 Scalability

The system should be designed so that:

1. Backend API instances are stateless.
2. Upload chunks are stored in MinIO, not local disk.
3. Media processing workers can scale horizontally.
4. Kafka can distribute processing jobs across workers.
5. Object storage can scale independently from API services.

## 13.2 Reliability

The system should support:

1. Retryable chunk upload.
2. Resumable upload.
3. Idempotent upload completion.
4. Idempotent media processing where possible.
5. Safe handling of failed processing jobs.
6. Clear status transitions.

## 13.3 Security

The system must ensure:

1. Only authenticated creators can upload.
2. Upload sessions are scoped to their creator.
3. Creators cannot access other creators' upload sessions.
4. Creators cannot manage other creators' videos.
5. Private videos are not publicly accessible.
6. Hidden videos are not publicly accessible.
7. Moderation status cannot be overridden by creators.
8. Backend validates file type, chunk metadata, and session ownership.

## 13.4 Cost Optimization

The platform prioritizes low-cost self-hosted infrastructure.

Phase 1 avoids expensive managed media services such as:

- AWS S3.
- AWS Elemental MediaConvert.
- Managed CDN-first architecture.

Preferred infrastructure:

- MinIO for object storage.
- FFmpeg for media processing.
- Kafka for event-driven messaging.
- PostgreSQL for relational data.
- Keycloak for identity.

## 13.5 Observability

Phase 1 should include basic observability for:

1. Upload session lifecycle.
2. Chunk upload failures.
3. Kafka event publishing.
4. Media worker processing time.
5. FFmpeg errors.
6. Video status transitions.
7. Storage operation failures.

Future observability may include distributed tracing, metrics dashboard, alerting, and structured audit logs.

---

## 14. System Boundaries

## 14.1 Phase 1 Logical Components

The system can be decomposed into:

```text
Viewing Site
Creator Studio
Backend API
Upload Service
Video Service
Media Worker
Kafka
PostgreSQL
MinIO
Keycloak
```

### 14.2 Viewing Site

Responsible for:

- Public video pages.
- HLS player integration.
- Public creator/video metadata display.

### 14.3 Creator Studio

Responsible for:

- Authenticated creator experience.
- Upload UI.
- Resume/retry UI.
- Video management UI.

### 14.4 Backend API

Responsible for:

- Authentication token validation.
- Authorization enforcement.
- Upload session APIs.
- Video metadata APIs.
- Public playback metadata APIs.
- Kafka event publishing.

### 14.5 Media Worker

Responsible for:

- Consuming Kafka processing events.
- Running FFmpeg.
- Generating HLS outputs.
- Generating thumbnails.
- Updating processing results.

---

## 15. Phase 1 API Capability Overview

This section lists capabilities, not final API contracts.

### 15.1 Upload APIs

Required capabilities:

```text
Create upload session
Upload chunk
Get upload session status
List missing chunks
Complete upload
Cancel/expire upload session
```

### 15.2 Video APIs

Required capabilities:

```text
Get public video by creator handle and video id
List my videos
Get my video detail
Update my video metadata
Update my video visibility
```

### 15.3 Playback APIs

Required capabilities:

```text
Get playback metadata
Get HLS manifest URL or playback source
```

### 15.4 Admin/Moderation APIs

Not required for Phase 1 UI, but the backend should reserve service-level logic for:

```text
Set video moderation status to HIDDEN
```

---

## 16. Data Flow Summary

## 16.1 Upload Data Flow

```text
Client
→ Backend API
→ Upload Session validation
→ MinIO temporary chunk bucket
→ Upload Session tracking in PostgreSQL
→ Complete upload request
→ MinIO merge/compose final original object
→ Video record created as PROCESSING
→ Kafka event published
```

## 16.2 Processing Data Flow

```text
Kafka topic
→ Media Worker
→ Read original video from MinIO
→ FFmpeg validate/extract/transcode
→ Store HLS outputs and thumbnail in MinIO
→ Update Video record
→ Publish processing result event
```

## 16.3 Playback Data Flow

```text
Guest opens /@creator/video-id
→ Viewing Site requests metadata
→ Backend validates public playback rule
→ Backend returns video metadata + HLS source
→ HLS player streams processed media
```

---

## 17. Future Roadmap

## 17.1 Phase 2 — Discovery and Engagement

Potential features:

- Search videos.
- Like videos.
- Comment on videos.
- Subscribe to creators.
- Creator public profile page.
- Playlist support.
- Basic view count.

Architecture preparation:

- Kafka events for video metadata changes.
- Search indexing pipeline.
- Activity events.
- Read-optimized query models.

## 17.2 Phase 3 — Moderation and Safety

Potential features:

- Report content.
- Admin moderation dashboard.
- Review queue.
- Moderation audit log.
- Creator appeal flow.
- Automated content scanning.

Architecture preparation:

- `moderation_status` already exists.
- Report-related event topics can be added.
- Admin role is already reserved.

## 17.3 Phase 4 — Analytics

Potential features:

- Creator analytics dashboard.
- View count.
- Watch time.
- Traffic source.
- Audience retention.
- Processing performance metrics.

Architecture preparation:

- Kafka can emit playback events.
- Analytics consumers can process events asynchronously.
- Aggregated data can be stored separately from transactional database.

## 17.4 Phase 5 — Scale and Delivery Optimization

Potential features:

- CDN integration.
- Signed playback URLs.
- Anti-hotlinking.
- Adaptive bitrate optimization.
- Regional storage strategy.
- Storage lifecycle policies.
- Cost monitoring.

Architecture preparation:

- Processed media object keys are already structured.
- HLS is already the primary playback format.
- MinIO-compatible object storage keeps S3-like abstraction.

## 17.5 Phase 6 — Organization and Team Support

Potential features:

- Organization accounts.
- Team members.
- Role-based access within creator workspace.
- Shared channels.
- Enterprise tenant isolation.

Architecture preparation:

- Current `creator_id` model can later be extended to `owner_type` / `owner_id` or workspace-based ownership.

---

## 18. Key Risks and Trade-offs

## 18.1 Backend Proxy Upload Risk

In Phase 1, backend receives chunks from the client and forwards them to MinIO.

Pros:

- Easier validation.
- Easier authorization control.
- Easier session ownership enforcement.
- Simpler client security model.

Cons:

- Backend still handles heavy upload traffic.
- API instances need sufficient network throughput.
- Direct-to-MinIO pre-signed upload may be needed later.

Mitigation:

- Design storage interfaces so upload flow can later switch to pre-signed URLs without rewriting business logic.

---

## 18.2 Kafka Complexity Risk

Kafka provides a strong foundation for event-driven architecture, analytics, search, and activity logs.

Pros:

- Long-term scalable event backbone.
- Good fit for future platform events.
- Supports multiple consumers for the same event stream.

Cons:

- More operational complexity than a simple job queue.
- Requires careful retry and dead-letter design.
- Requires idempotent consumers.

Mitigation:

- Keep Phase 1 topics minimal.
- Use clear event contracts.
- Implement idempotency for media processing.
- Add dead-letter topic strategy early.

---

## 18.3 Self-hosted Media Processing Risk

Using FFmpeg and MinIO gives cost control and learning value.

Pros:

- Low infrastructure cost.
- Full control over media pipeline.
- Good learning value.
- No dependency on expensive managed media services.

Cons:

- Requires careful worker resource management.
- FFmpeg jobs are CPU-intensive.
- Failure handling must be implemented manually.
- Scaling media workers can become complex.

Mitigation:

- Run media workers separately from API services.
- Limit concurrency per worker.
- Track processing status clearly.
- Add retry and failure reason logging.

---

## 18.4 Moderation Scope Risk

Phase 1 includes only moderation status support, not a full moderation workflow.

Risk:

- Public user-generated content may require reporting and admin review sooner than expected.

Mitigation:

- Keep `moderation_status` in the initial data model.
- Reserve admin role.
- Design visibility rules to already respect moderation state.

---

## 19. Acceptance Criteria for MVP Phase 1

Phase 1 can be considered successful when:

1. A guest can watch a public ready video without logging in.
2. A user can register/login through Keycloak.
3. A creator can upload a video using chunked upload.
4. Upload can resume after interruption by uploading only missing chunks.
5. Chunks are stored in MinIO temporary storage.
6. Backend can finalize uploaded chunks into an original video object.
7. A Kafka event is emitted after upload completion.
8. Media Worker consumes the event and processes the video asynchronously.
9. FFmpeg generates thumbnail and HLS outputs.
10. Processed assets are stored in MinIO.
11. Video status transitions from `PROCESSING` to `READY` or `FAILED`.
12. Public playback is available only when the video is `READY`, `PUBLIC`, and `NORMAL`.
13. Creator can view and manage their own videos in Studio.
14. Creator cannot access or manage another creator's videos.
15. Hidden videos are not publicly viewable and cannot be made public by creators.

---

## 20. Open Questions for Follow-up Documents

The following questions should be resolved in the Architecture Design Document or DB Schema document:

1. What exact maximum file size should Phase 1 support?
2. What chunk size should the frontend use?
3. Should chunk metadata be stored as rows, JSON, bitmap, Redis cache, or object listing from MinIO?
4. Should upload completion use MinIO compose/multipart APIs or application-managed merge logic?
5. What exact Kafka topic naming convention should be used?
6. What retry and dead-letter policy should media processing use?
7. Should HLS files be public-read in MinIO or served through signed/backend-controlled URLs?
8. What video player should the frontend use?
9. What database migration tool should be used?
10. What is the deployment target for local development and production-like environments?

---

## 21. Final MVP Summary

VideoHUB Phase 1 is a focused creator-first video platform MVP.

It does not attempt to build the full YouTube-like social layer yet. Instead, it validates the hardest technical foundation first:

```text
Large upload
Chunk retry/resume
Stateless backend upload architecture
MinIO object storage
Kafka-based async processing
FFmpeg transcoding
HLS playback
Creator-owned video management
Public/private visibility
Moderation-aware playback rules
```

This gives the product a clean base for future expansion into search, subscriptions, comments, reporting, analytics, CDN delivery, and enterprise-style tenant models without overloading the first implementation phase.