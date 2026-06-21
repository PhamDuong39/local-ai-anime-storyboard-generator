# Tech Stack — VideoHUB Phase 1

## 1. Overview

VideoHUB Phase 1 uses a self-hosted, cost-optimized, event-driven architecture focused on proving the full media lifecycle: large chunked upload, durable object storage, asynchronous FFmpeg processing, HLS playback, and creator-owned video management. The platform avoids expensive managed media services in Phase 1 by using MinIO for S3-compatible storage, Kafka for media workflow events, PostgreSQL for transactional state, Redis for lightweight coordination/idempotency, and Keycloak for identity. The backend remains stateless by streaming upload chunks and merge output through object storage instead of relying on local disk.

---

## 2. Backend Services

### 2.1 Service Summary

| Service | Runtime / Language | Framework | Primary Responsibility | Scaling Model |
|---|---:|---|---|---|
| API Server | Java 25.0.3, Eclipse Temurin | Spring Boot 4.0.6 | Public metadata APIs, Creator Studio APIs, upload session APIs, chunk intake, application-managed streaming merge, playback authorization, Kafka event publishing | Horizontally scalable stateless replicas |
| Media Worker | Java 25.0.3, Eclipse Temurin | Spring Boot 4.0.6 | Kafka consumer for processing jobs, FFmpeg orchestration, metadata extraction, thumbnail generation, HLS packaging, video status updates | Horizontally scalable worker replicas; fixed FFmpeg concurrency per worker |

### 2.2 Backend Platform Versions

| Technology | Version | Used By | Notes |
|---|---:|---|---|
| Java / JDK | Eclipse Temurin `25.0.3+9` | API Server, Media Worker | Use Java 25 virtual threads for high-concurrency I/O paths, especially upload chunk streaming and MinIO object streaming. |
| Spring Boot | `4.0.6` | API Server, Media Worker | Main application framework. Use Spring Boot dependency management as the source of truth for managed Spring dependencies. |
| Spring Framework | Boot-managed, Spring Framework 7.x line | API Server, Media Worker | Do not override unless needed for a security patch. |
| Spring Security | Boot-managed, Spring Security 7.x line | API Server | OAuth2 Resource Server for validating Keycloak JWT access tokens. |
| Spring Web MVC | Boot-managed | API Server | REST APIs and streaming upload endpoints. Prefer servlet stack + virtual threads over reactive complexity for Phase 1. |
| Spring Data JPA | Boot-managed | API Server, Media Worker | Transactional CRUD for creators, videos, upload sessions, chunk rows, media assets, and outbox/event records if added. |
| Spring for Apache Kafka | Boot-managed | API Server, Media Worker | Kafka producers/consumers, retry handling, DLQ publishing. |
| Flyway | `12.6.0` | API Server startup / CI | Versioned PostgreSQL schema migrations. |
| MinIO Java SDK | `io.minio:minio:9.0.0` | API Server, Media Worker | S3-compatible bucket/object operations. |
| PostgreSQL JDBC Driver | Boot-managed | API Server, Media Worker | Database connectivity. |
| Jackson | Boot-managed | API Server, Media Worker | JSON serialization for APIs and Kafka event payloads. |
| Micrometer + Spring Boot Actuator | Boot-managed | API Server, Media Worker | Health checks, basic metrics, and operational visibility. |
| Logback + SLF4J | Boot-managed | API Server, Media Worker | Structured application logging. |
| Testcontainers | `2.0.5` | Automated tests | Integration tests for PostgreSQL, Redis, Kafka, MinIO-compatible behavior where practical. |

### 2.3 API Server Responsibilities

| Area | Decision |
|---|---|
| Upload limit | Max file size: `5GB`. |
| Chunk size | `10MB` fixed client chunk size for Phase 1. |
| Chunk metadata | Store each chunk as a PostgreSQL row keyed by `upload_session_id + chunk_index`. |
| Upload transport | Browser uploads chunks to backend API; backend streams chunk body directly to `videohub-temp-uploads` in MinIO. |
| Merge strategy | Application-managed streaming merge: backend opens chunk objects from MinIO in order and pipes bytes into the final original object without full-file buffering in memory. |
| Streaming execution | Use Java virtual threads for blocking I/O endpoints and MinIO streaming paths. |
| Upload session rate limiting | Redis-backed counters per creator/session/IP where useful. |
| Playback authorization | Return HLS URL only when `status = READY`, `visibility = PUBLIC`, and `moderation_status = NORMAL`. |
| Kafka events | Publish events using `videohub.<domain>.<event>` naming. |

### 2.4 Media Worker Responsibilities

| Area | Decision |
|---|---|
| Trigger | Consume `videohub.upload.completed`. |
| Processing style | Pull original object from MinIO, run FFmpeg in isolated worker process, write generated HLS/thumbnail artifacts back to MinIO. |
| Concurrency | Default `1` FFmpeg job per worker container in local/dev; configure by CPU count in production-like environments. |
| Idempotency | Use Redis idempotency key cache: `media-processing:{video_id}:{source_etag}`. Keep DB status transitions idempotent. |
| Retry policy | 3 retries with exponential backoff, then publish to DLQ topic. |
| DLQ pattern | `videohub.<domain>.<event>.dlq`, for example `videohub.video.processing.dlq`. DLQ is a standalone dead-letter destination, not a suffix of the `.failed` notification topic. |
| Failure handling | Set `video.status = FAILED`, persist failure reason, and emit processing failed event. |

### 2.5 Initial Kafka Topics

| Topic | Producer | Consumer | Purpose |
|---|---|---|---|
| `videohub.upload.completed` | API Server | Media Worker | Upload finalized and original object is ready for processing. This is the sole trigger for Media Worker in Phase 1. |
| `videohub.video.processing.completed` | Media Worker | API Server / future analytics | Processing success: HLS and thumbnail assets are available in MinIO. |
| `videohub.video.processing.failed` | Media Worker | API Server / future ops | Processing failure notification after all retries exhausted before DLQ routing. |
| `videohub.video.processing.dlq` | Kafka error handler | Manual ops / future replay tool | Dead-letter destination for poison messages after 3 retries. Standalone topic, not a suffix of the `.failed` notification topic. |

---

## 3. Frontend

| Technology | Version | Role | Notes |
|---|---:|---|---|
| Node.js | `24.x LTS` | Frontend runtime/tooling | Use an LTS runtime for local dev and build consistency. |
| TypeScript | `5.9.x` | Frontend language | Strict mode enabled. |
| React | `19.2.x` | UI library | Aligns with the current React 19 line and Next.js App Router patterns. |
| Next.js | `16.2.6` | Frontend framework | Use App Router, server components where useful, and client components for upload/player interactions. |
| Video.js | `10.x` | Browser video player | Primary player abstraction for HLS playback UI. |
| hls.js | `1.6.16` | HLS playback engine | Use through Video.js integration or direct fallback where Video.js integration needs manual control. |
| Tailwind CSS | `4.x` | Styling | Fast MVP UI implementation with utility classes. |
| shadcn/ui | Latest generated components pinned in repo | UI components | Copy generated components into source; do not treat as runtime dependency. |
| TanStack Query | `5.x` | Server state | Upload session status polling, video list queries, mutation handling. |
| Axios or Fetch wrapper | Native `fetch` preferred | HTTP client | Use `fetch` first; add Axios only if upload progress handling becomes cleaner with it. |
| Zod | `4.x` | Client-side validation | Form and API response validation where useful. |

### Frontend Applications

| App Area | Route Pattern | Responsibility |
|---|---|---|
| Public Viewing Site | `/@{handle}/{videoId}` | Public metadata page, HLS player, unavailable/private/processing states. |
| Creator Studio | `/studio` | Authenticated video list, upload UI, retry/resume UI, video metadata management. |
| Auth Redirects | `/auth/*` or NextAuth/Keycloak callback paths | SSO callback and session handling depending on selected client auth approach. |

### Upload UX Decisions

| Area | Decision |
|---|---|
| Browser chunking | Use `Blob.slice()` with 10MB chunks. |
| Resume | Query backend for missing chunk indexes before re-uploading. |
| Retry | Retry failed chunk uploads client-side with exponential backoff and max attempt count. |
| Progress | Calculate progress from uploaded chunk count confirmed by backend, not only browser transfer progress. |
| Large file guard | Reject files over `5GB` client-side before creating upload session. |

---

## 4. Infrastructure & Middleware

| Component | Version / Image Recommendation | Role | Phase 1 Configuration |
|---|---:|---|---|
| PostgreSQL | `18.4` | Primary relational database | Store creators, videos, upload sessions, chunk rows, media asset metadata, processing status, moderation status. |
| Redis | `8.0.18` | Lightweight cache/coordination | Upload session rate limiting and Kafka consumer idempotency key cache. No source of truth data. |
| Apache Kafka | `3.9.2` | Event broker | Use because ZooKeeper mode is required by the confirmed local stack; Kafka 4.x is intentionally not used in Phase 1. |
| Apache ZooKeeper | `3.9.5` | Kafka coordination for Phase 1 local/dev stack | Required only while Kafka runs in ZooKeeper mode. Plan migration to KRaft later. |
| MinIO | `RELEASE.2025-10-15T17-29-55Z` | S3-compatible object storage | Stores temporary chunks, originals, processed HLS, thumbnails. |
| Keycloak | `26.6.1` | Identity provider | Username/password auth, Google SSO, JWT issuance, roles. |
| Docker Compose | Compose plugin `v2.37.x` or newer | Local development | Runs PostgreSQL, Redis, ZooKeeper, Kafka, MinIO, Keycloak, API Server, Media Worker. |

### Local Docker Compose Services

| Service Name | Image Pin | Port Suggestion | Notes |
|---|---|---:|---|
| `postgres` | `postgres:18.4` | `5432` | One database for app, separate Keycloak database/schema recommended. |
| `redis` | `redis:8.0.18` | `6379` | Enable append-only file only if local debugging needs persistence. |
| `zookeeper` | `zookeeper:3.9.5` | `2181` | Single-node local only. |
| `kafka` | `bitnami/kafka:3.9.2` or equivalent Apache Kafka 3.9.2 image | `9092` | Configure external listener for host development. |
| `minio` | `minio/minio:RELEASE.2025-10-15T17-29-55Z` | `9000`, `9001` | Console on 9001. Pre-create buckets at startup. |
| `keycloak` | `quay.io/keycloak/keycloak:26.6.1` | `8080` | Dev mode locally; import realm config from repo. |
| `api-server` | Built from repo | `8081` | Depends on Postgres, Redis, Kafka, MinIO, Keycloak. |
| `media-worker` | Built from repo with FFmpeg installed | n/a | Depends on Postgres, Redis, Kafka, MinIO. |

---

## 5. Media Processing

| Technology | Version | Role |
|---|---:|---|
| FFmpeg | `8.0` | Metadata extraction, thumbnail generation, HLS transcoding. |
| ffprobe | `8.0` | Source media validation and metadata extraction. |
| HLS protocol | HLS VOD, MPEG-TS segments for Phase 1 | Broad player compatibility and simple MinIO hosting. |
| Video codecs | H.264 / AVC | Max compatibility across browsers/devices. |
| Audio codec | AAC-LC | Standard HLS-compatible audio track. |
| Segment duration | `6s` target duration | Balanced startup speed and object count. |
| Playlist type | VOD | Static processed assets after upload completes. |

### Phase 1 HLS Output Ladder

Generate only variants that do not upscale beyond the source resolution.

| Variant | Resolution | Video Bitrate Target | Audio | Output Path |
|---|---:|---:|---|---|
| 360p | `640x360` | `800k` | AAC 96k | `hls/360p/index.m3u8` |
| 720p | `1280x720` | `2800k` | AAC 128k | `hls/720p/index.m3u8` |
| 1080p | `1920x1080` | `5000k` | AAC 160k | `hls/1080p/index.m3u8` |
| Master playlist | n/a | n/a | n/a | `hls/master.m3u8` |
| Thumbnail | source-derived JPEG | n/a | n/a | `default.jpg` |

### Variant Generation Rules

| Source Video | Generated Variants |
|---|---|
| Less than 720p but at least 360p | 360p only |
| 720p source | 360p, 720p |
| 1080p or higher source | 360p, 720p, 1080p |
| Below 360p | Keep nearest safe lower/original-size profile; mark as low-resolution but still playable if valid. |

### Recommended FFmpeg Behavior

| Area | Decision |
|---|---|
| Temporary processing workspace | Use container-local ephemeral disk only for FFmpeg working files, not for durable uploaded chunks. |
| Input source | Stream/copy original object from MinIO to worker workspace before FFmpeg for simpler failure isolation. For later optimization, evaluate streaming input. |
| Output upload | Write HLS outputs to worker workspace, then upload directory tree to MinIO. |
| Cleanup | Delete worker temp directory after success/failure. |
| Failure logging | Capture FFmpeg stderr and persist summarized failure reason to DB. |

---

## 6. Authentication

| Area | Decision |
|---|---|
| Identity Provider | Keycloak `26.6.1`. |
| Token type | JWT access token. |
| Protocol | OAuth 2.1 / OpenID Connect style browser login through Keycloak. |
| SSO | Google SSO configured as Keycloak Identity Provider. |
| Backend validation | Spring Security OAuth2 Resource Server validates issuer, audience/client, signature, expiry, and roles. |
| Roles | `GUEST`, `CREATOR`, `ADMIN`. |
| Creator identity mapping | `creator.keycloak_user_id` maps to Keycloak subject (`sub`). |
| Frontend auth | Use Keycloak Authorization Code + PKCE flow. For Next.js, use a server-side session wrapper only if needed for route protection; backend remains the real authorization authority. |

### Authorization Rules Enforced by Backend

| Rule | Enforcement |
|---|---|
| Public playback | Only return playback metadata/HLS URL when `READY + PUBLIC + NORMAL`. |
| Creator ownership | Every Studio write/read checks `creator_id` ownership. |
| Upload ownership | Upload session belongs to authenticated creator. |
| Moderation lock | Creators cannot set `moderation_status` and cannot make `HIDDEN` videos public. |

---

## 7. Storage Layout

### MinIO Buckets

| Bucket | Access Policy | Contains | Lifecycle / Cleanup |
|---|---|---|---|
| `videohub-temp-uploads` | Private | Upload chunks before finalization | Expire failed/abandoned sessions after configured TTL. Delete after successful merge. |
| `videohub-originals` | Private | Final original uploaded videos | Retain while video exists. Never public-read. |
| `videohub-processed` | Public-read | HLS master playlists, variant playlists, media segments | Backend exposes URL only after playback rule validation. Bucket is public-read for Phase 1 simplicity. |
| `videohub-thumbnails` | Public-read | Generated thumbnails | Safe to expose for public videos; backend still controls metadata visibility. |

### Object Key Structure

| Asset | Bucket | Object Key Pattern |
|---|---|---|
| Upload chunk | `videohub-temp-uploads` | `{upload_session_id}/chunks/{chunk_index}` |
| Original video | `videohub-originals` | `{creator_id}/{video_id}/source.{ext}` |
| HLS master playlist | `videohub-processed` | `{creator_id}/{video_id}/hls/master.m3u8` |
| 360p playlist | `videohub-processed` | `{creator_id}/{video_id}/hls/360p/index.m3u8` |
| 720p playlist | `videohub-processed` | `{creator_id}/{video_id}/hls/720p/index.m3u8` |
| 1080p playlist | `videohub-processed` | `{creator_id}/{video_id}/hls/1080p/index.m3u8` |
| HLS segment | `videohub-processed` | `{creator_id}/{video_id}/hls/{quality}/segment_{number}.ts` |
| Thumbnail | `videohub-thumbnails` | `{creator_id}/{video_id}/default.jpg` |

### Access Model

Processed HLS assets are public-read in MinIO for Phase 1, but discoverability is controlled by the backend. The frontend receives the HLS URL only after the backend validates the playback rules. This is not strong private-media protection; it is an MVP trade-off to avoid signed URL complexity in Phase 1.

---

## 8. Developer Tooling

| Tool | Version | Role |
|---|---:|---|
| Docker Engine | `26.x` or newer | Container runtime. |
| Docker Compose Plugin | `v2.37.x` or newer | Local multi-service orchestration. |
| Gradle | `8.x` (Kotlin DSL) | Java build tool. Multi-module project managed via `settings.gradle.kts` at root and per-subproject `build.gradle.kts`. |
| Flyway | `12.6.0` | Database migration runner. |
| Node.js | `24.x LTS` | Frontend build/runtime tooling. |
| pnpm | `10.x` | Frontend package manager. |
| GitHub Actions | Current hosted runners | CI pipeline for build/test/lint/migration validation. |
| Testcontainers | `2.0.5` | Backend integration tests. |

### Local Dev Workflow

1. Copy `.env.example` to `.env`.
2. Start infrastructure: `docker compose up -d postgres redis zookeeper kafka minio keycloak`.
3. Run bucket bootstrap script to create MinIO buckets and access policies.
4. Import Keycloak realm and Google SSO placeholders for local/dev.
5. Run backend migrations with Flyway.
6. Start API Server and Media Worker through Docker Compose or IDE profiles.
7. Start frontend with `pnpm dev`.
8. Upload a small sample video, verify chunk rows, original object, Kafka event, HLS output, and public playback.

### Repository Layout Recommendation

```text
videohub/
  backend/
    settings.gradle.kts          ← root multi-module config
    build.gradle.kts             ← shared dependency versions (version catalog or BOM)
    api-server/
      build.gradle.kts
    media-worker/
      build.gradle.kts
    common-domain/
      build.gradle.kts
    common-events/
      build.gradle.kts
  frontend/
  infra/
    docker-compose.yml
    minio/
    keycloak/
    kafka/
  db/
    migration/
  docs/
    prd_video_hub.md
    techstack.md
```

---

## 9. Decision Rationale

| Decision | Rationale |
|---|---|
| Java 25 + Spring Boot 4.0.6 | Matches the confirmed backend direction and gives modern Java features, especially virtual threads, while keeping the framework mainstream and maintainable. |
| Servlet stack + virtual threads instead of full reactive stack | Upload and object-storage streaming are I/O-heavy, but the team can keep simpler imperative code and still achieve high concurrency. |
| Separate API Server and Media Worker | FFmpeg is CPU-heavy and failure-prone compared with normal API traffic. Keeping it out of the API process protects request latency and simplifies worker scaling. |
| PostgreSQL chunk rows instead of Redis-only chunk state | Upload progress is durable and queryable after restarts. Redis remains a cache/rate-limit/idempotency tool, not the source of truth. |
| Application-managed streaming merge | Keeps backend stateless while avoiding full-file memory buffering. It also keeps merge behavior portable across S3-compatible storage implementations. |
| MinIO instead of AWS S3 | Keeps Phase 1 self-hosted and cost-controlled while preserving S3-compatible object storage semantics for future migration. |
| Public-read HLS bucket in Phase 1 | Simplifies playback and avoids signed URL/token gateway complexity. Backend still controls URL issuance using `READY + PUBLIC + NORMAL` rules. |
| Kafka 3.9.2 instead of Kafka 4.x | The confirmed local stack includes ZooKeeper. Kafka 4.x removes ZooKeeper mode, so Kafka 3.9.2 is the safer Phase 1 choice. |
| Kafka instead of a simple job queue | More operational overhead, but it creates the event backbone needed later for analytics, search indexing, activity logs, moderation, and notification workflows. |
| Redis for idempotency cache | Fast TTL-based keys are enough for duplicate Kafka message protection. Durable status still lives in PostgreSQL. |
| Keycloak instead of custom auth | Avoids building login, token issuance, role management, and Google SSO from scratch. |
| FFmpeg instead of managed transcoding | Much lower cost and maximum control for the MVP, with the trade-off that worker resource management must be implemented carefully. |
| HLS instead of progressive MP4 playback | HLS provides adaptive streaming and is the right foundation for future CDN-backed delivery. |
| Video.js + hls.js | Gives a stable player UI abstraction with explicit HLS support across browsers. |
| Gradle + Kotlin DSL instead of Maven | Multi-module project benefits from Gradle's flexible dependency sharing across `api-server`, `media-worker`, `common-domain`, and `common-events`. Kotlin DSL gives IDE autocomplete and compile-time safety for build scripts, which Maven XML does not provide. |
| Flyway instead of Hibernate-only schema generation | Production schema changes need versioned, reviewable migrations. Hibernate can validate mappings but should not own production DDL. |
| Docker Compose for local development | The platform has many moving parts; Compose gives every developer a reproducible local stack without needing Kubernetes early. |

---

## 10. Deferred Decisions

| Deferred Technology / Capability | Phase 1 Decision | Reserved Future Direction |
|---|---|---|
| CDN | Not used | Add CDN in front of `videohub-processed` and `videohub-thumbnails` in scale phase. |
| Signed HLS URLs | Not used | Introduce signed URLs or tokenized media gateway for private/protected playback. |
| Direct-to-MinIO browser upload | Not used | Add pre-signed multipart/chunk upload later to reduce API bandwidth load. |
| AWS S3 | Not used | Keep S3-compatible abstraction so MinIO can be swapped/mirrored later. |
| AWS Elemental MediaConvert / managed transcoding | Not used | Consider only if self-hosted FFmpeg scaling becomes too expensive operationally. |
| Kubernetes | Not required for Phase 1 local dev | Add when production deployment requires rolling deploys, worker autoscaling, and service discovery. |
| Kafka KRaft mode | Not used because ZooKeeper is confirmed for Phase 1 | Migrate from Kafka 3.9.x + ZooKeeper to Kafka 4.x+ KRaft after local/dev and ops model are ready. |
| Schema Registry | Not used | Add when multiple event consumers and stricter event compatibility become necessary. |
| OpenSearch / Elasticsearch | Not used | Add for full-text video search in Phase 2 discovery. |
| Analytics warehouse | Not used | Add ClickHouse, BigQuery, or similar when playback events and creator analytics ship. |
| DRM | Not used | Reserve for premium/private content later. |
| Live streaming | Not used | Requires separate ingest, segmenting, latency, and moderation model. |
| Custom thumbnail upload | Not used | Add after generated thumbnails and metadata editing are stable. |
| Advanced moderation tooling | Not built | Data model reserves `moderation_status`; admin review workflows can be added later. |
| Organization/team tenancy | Not built | Current `creator_id` model can evolve to `owner_type / owner_id` or workspace ownership. |

---

## Final Phase 1 Stack Snapshot

| Layer | Chosen Stack |
|---|---|
| Backend | Java 25.0.3, Spring Boot 4.0.6, Spring Security, Spring Data JPA, Spring Kafka |
| Frontend | Next.js 16.2.6, React 19.2.x, TypeScript 5.9.x, Video.js 10.x, hls.js 1.6.16 |
| Database | PostgreSQL 18.4 |
| Cache / Coordination | Redis 8.0.18 |
| Event Broker | Kafka 3.9.2 + ZooKeeper 3.9.5 |
| Object Storage | MinIO RELEASE.2025-10-15T17-29-55Z |
| Identity | Keycloak 26.6.1, JWT, OIDC Authorization Code + PKCE, Google SSO |
| Media | FFmpeg 8.0, HLS VOD, H.264/AAC, 360p/720p/1080p ladder |
| Dev Environment | Docker Compose v2.37.x+, Gradle 8.x (Kotlin DSL), Flyway 12.6.0, Testcontainers 2.0.5 |