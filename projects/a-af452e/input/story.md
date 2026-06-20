# VideoHub — Design Summary


---

## 1. Business Requirements Document

### 1.1 Tổng quan
Platform video công khai dạng **single-tenant**, cho phép bất kỳ ai đăng ký tài khoản, upload video và xem nội dung. Không yêu cầu đăng nhập để xem video Public. Sử dụng Keycloak làm Identity Provider, hỗ trợ đăng nhập bằng Google SSO.
tạo Video domain entity trong domain/model.Video
- **Scale mục tiêu:** Khởi đầu ~100 user → 100,000 user

---

### 1.2 Người dùng & Vai trò

| Role | Mô tả |
|---|---|
| Guest | Chưa đăng nhập — chỉ xem video Public, không tương tác |
| User | Đã đăng nhập — vừa là Viewer vừa là Creator, sở hữu 1 kênh |
| Admin | Quản trị viên — quản lý nội dung và tài khoản |

Không có role riêng biệt Viewer / Creator. Mọi User đều có thể upload và xem.

---

### 1.3 Auth & Keycloak

- Keycloak đứng độc lập (single realm: `videohub`)
- Hỗ trợ đăng ký username/password và đăng nhập qua **Google OAuth2**
- Flow: Authorization Code + PKCE (browser), Client Credentials (service-to-service)
- Clients: `studio-app`, `viewing-app`, `admin-app`
- Roles quản lý trong Keycloak: `user`, `admin`

---

### 1.4 Kênh (Channel)

- Mỗi User có đúng **1 kênh**, tự động tạo ngay khi đăng ký
- Tên kênh mặc định lấy từ display name Keycloak, User có thể đổi sau
- Creator có thể chỉnh sửa: tên kênh, avatar, mô tả kênh

---

### 1.5 Video

**Upload & Trạng thái:**

```
Creator upload → Hệ thống xử lý (transcode) → Tự động PUBLIC ngay sau khi xong
```

**Visibility levels:**

| Mức | Ai xem được |
|---|---|
| PUBLIC | Tất cả, kể cả Guest |
| PRIVATE | Chỉ mình Creator |

**Creator được chỉnh sửa sau khi publish:**
- Tiêu đề, mô tả, tag (tự do, không cần Admin duyệt)
- Thumbnail
- Đổi trạng thái PUBLIC ↔ PRIVATE

**Không được** chỉnh sửa file video gốc — phải xóa và upload lại.

**Không giới hạn** dung lượng, thời lượng, số lượng video.

**Khi User xóa tài khoản:** `isActive = false` → video của kênh tự động ẩn (không xóa vật lý).

---

### 1.6 Xem Video

- Guest xem được video Public không cần đăng nhập
- Lưu vị trí xem (timestamp ms) mỗi ~10 giây khi đang phát
- Lần sau mở lại: hiển thị prompt **"Tiếp tục xem từ x:xx không?"**
- Watch History lưu theo tài khoản

---

### 1.7 Trang Home & Khám phá

- Feed video: **Mới nhất** và **Phổ biến nhất**
- Tìm kiếm theo từ khóa (title, description, tag)
- Lọc theo **tag / danh mục** (tag do Creator tự tạo tự do)
- Không có: Sidebar video liên quan, Playlist

---

### 1.8 Tương tác xã hội

| Tính năng | Yêu cầu login | Ghi chú |
|---|---|---|
| Like / Dislike | Có | Toggle: gọi lại cùng type → bỏ reaction |
| Comment & Reply | Có | Reply 1 cấp, không nested sâu hơn |
| Subscribe kênh | Có | Toggle on/off |
| Chia sẻ | Không | Copy link, không tích hợp mạng xã hội |

**Xóa comment:**
- Creator được xóa comment trên video của mình
- Nếu comment bị xóa có reply: reply đầu tiên được promote lên làm comment cha, các reply còn lại giữ nguyên thứ tự

---

### 1.9 Notification (In-app only, không email)

| Sự kiện | Người nhận |
|---|---|
| Video upload xử lý xong | Creator |
| Kênh subscribe có video mới | Các subscriber của kênh đó |

---

### 1.10 Analytics (dành cho Creator)

- Lượt xem (view count)
- Số like / dislike / comment
- Watch time trung bình

---

### 1.11 Admin

Quản lý qua Keycloak role `admin`:
- Xóa hoặc ẩn video vi phạm
- Khóa / vô hiệu hóa tài khoản User
- Dashboard thống kê toàn hệ thống
- Xử lý report từ User (approve/reject)

**Report flow:** User báo cáo video → vào queue Admin → Admin duyệt → approve (ẩn/xóa video) hoặc reject (giữ nguyên)

---

### 1.12 Hai Site chính

**Site 1 — Studio (Upload Site):**
- Upload video (title, description, thumbnail, tag, visibility)
- Quản lý danh sách video (bao gồm PRIVATE, PROCESSING, FAILED)
- Chỉnh sửa metadata / thumbnail / visibility
- Xóa video
- Xem analytics từng video
- Cài đặt kênh (tên, avatar, mô tả)

**Site 2 — Viewing Site:**
- Trang Home với feed video
- Tìm kiếm & lọc theo tag
- Trang xem video (player + like/dislike/comment/subscribe/report)
- Trang kênh Creator
- Watch history & resume
- In-app notifications

---

### 1.13 Out of Scope

- Monetization / quảng cáo
- Subtitle / phụ đề tự động
- Bulk upload
- Playlist
- Video liên quan (sidebar)
- Multi-tenant
- Email notification
- Live streaming

---

## 2. User Flow Diagrams

### Flow 1 — Auth & Khởi tạo tài khoản

```
User truy cập
    ↓
Keycloak Login (Username/Password hoặc Google SSO)
    ↓
Lần đầu? ──Có──→ Tự động tạo Channel (tên = display name)
    ↓                          ↓
Không                          ↓
    ↓←─────────────────────────┘
Đăng nhập thành công (JWT token)
    ↓
Redirect về trang trước

[Nhánh phụ] Tài khoản bị khóa → Hiện thông báo lỗi
```

---

### Flow 2 — Upload Video (Studio Site)

```
Creator vào Studio → Upload
    ↓
Chọn file + nhập title, desc, tag, visibility
    ↓
Upload theo chunk lên server (Resumable)
    ↓
Hệ thống xử lý transcode → status = PROCESSING
    ↓
Thành công? ──Không──→ Báo lỗi → In-app notify Creator → [Retry]
    ↓
Có
    ↓
Video tự động PUBLIC → In-app notify Creator
    ↓
Subscribers nhận in-app notify "Kênh X vừa đăng video mới"
```

---

### Flow 3 — Xem Video (Viewing Site)

```
User mở trang xem video
    ↓
Video PRIVATE? ──Có──→ Đúng là Creator? ──Không──→ 404 / No access
    ↓
PUBLIC
    ↓
User đã đăng nhập + có watch history?
    ├─ Guest ──→ Phát từ đầu, không lưu progress
    └─ Có ──→ Hiện prompt "Tiếp tục từ x:xx?"
                ↓
            Video đang phát → Lưu timestamp mỗi ~10 giây
                ↓
            User actions (yêu cầu login): Like · Dislike · Comment · Subscribe · Report
                ↓
            Guest → Hiện prompt "Đăng nhập để tương tác"
```

---

### Flow 4a — Xóa Comment

```
Creator nhấn Xóa comment trên video của mình
    ↓
Comment có Reply?
    ├─ Không → Xóa hoàn toàn
    └─ Có → Xóa comment gốc
              → Reply đầu tiên → thành Comment mới (parent_id = null)
              → Các Reply còn lại giữ nguyên thứ tự bên dưới
```

---

### Flow 4b — Admin xử lý Report

```
User report video vi phạm (chọn lý do + submit)
    ↓
Report vào queue Admin dashboard
    ↓
Admin xem xét
    ├─ Vi phạm → Xóa hoặc Ẩn video / Khóa tài khoản Creator
    └─ Không vi phạm → Đóng report, video giữ nguyên
```

---

## 3. Data Model (Final)

### Entities & Quan hệ

| Entity | Mô tả |
|---|---|
| USER | Tài khoản, liên kết với Keycloak qua `keycloak_id` |
| CHANNEL | 1-1 với USER, có tên/avatar/mô tả riêng |
| VIDEO | Thuộc CHANNEL, có status và visibility |
| VIDEO_TAG | Tag tự do của video (1 video nhiều tag) |
| VIDEO_FILE | Các bản transcode (1080p/720p/...) của 1 video |
| WATCH_HISTORY | Lịch sử xem, lưu `position_ms` |
| LIKE | Like/Dislike (field `type`), unique per user+video |
| COMMENT | Comment và reply (self-reference qua `parent_id`) |
| SUBSCRIPTION | User subscribe kênh |
| NOTIFICATION | In-app notification |
| REPORT | Report video vi phạm |
| UPLOAD_SESSION | Tạo session upload video |

### Các quyết định thiết kế quan trọng

- **USER vs CHANNEL tách biệt** — khi user xóa tài khoản (`isActive=false`), video tự ẩn mà không cần update từng record
- **VIDEO.status** — `PROCESSING | READY | FAILED`. Chỉ `READY` mới hiển thị trên Viewing Site
- **VIDEO.visibility** — `PUBLIC | PRIVATE | HIDDEN` (HIDDEN do Admin set)
- **UPLOAD_SESSION.status** — `INIT | UPLOADING | COMPLETED | FAILED` (Upload theo từng chunk, set status upload, sau scale có thể sử dụng để kiểm tra chunk missing(Resume API))
- **VIDEO_FILE** — mỗi resolution là 1 row riêng (1080p, 720p, 480p, 360p)
- **COMMENT.parent_id** — self-reference, soft delete bằng `is_deleted = true`
- **LIKE.type** — `LIKE | DISLIKE`, tránh 2 bảng
- **WATCH_HISTORY.position_ms** — lưu millisecond, không lưu segment ID
- **NOTIFICATION.ref_id** — trỏ đến entity liên quan để build deep link

### Schema chính

```sql
USER        (id, keycloak_id UK, email, role, is_active, created_at)
CHANNEL     (id, user_id FK, name, description, avatar_url, created_at)
VIDEO       (id, channel_id FK, title, description, visibility, status, thumbnail_url, duration_seconds, view_count, published_at, created_at)
VIDEO_TAG   (video_id FK, tag)
VIDEO_FILE  (id, video_id FK, resolution, file_url, codec, file_size)
UPLOAD_SESSION(id, video_id FK, user_id FK, total_chunks, uploaded_chunks, status, created_at, updated_at)
WATCH_HISTORY (id, user_id FK, video_id FK, position_ms, last_watched_at)
LIKE        (user_id FK, video_id FK, type, created_at)
COMMENT     (id, video_id FK, user_id FK, parent_id FK, content, is_deleted, created_at)
SUBSCRIPTION (subscriber_id FK, channel_id FK, subscribed_at)
NOTIFICATION (id, user_id FK, type, content, ref_id, is_read, created_at)
REPORT      (id, reporter_id FK, video_id FK, reason, status, created_at)
```

---

## 4. Technical Architecture

### 4.1 System Overview

```
┌─────────────────────────────────────────────────────┐
│ Clients                                             │
│  Studio Site (Next.js) │ Viewing Site │ Admin       │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────┐   ┌──────────────────────┐
│ API Gateway (Nginx/Kong) │↔│ Keycloak 24+          │
│ Rate limit · JWT · Route │   │ SSO · Google · JWT   │
└──────────────┬───────────┘   └──────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│ Core Services (Java Spring Boot 3.x)                │
│  user-service │ video-service │ stream-service       │
│  interaction  │ notification  │ search               │
│  analytics    │ admin-service │ transcode-worker     │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│ Apache Kafka                                        │
│  video.uploaded · video.ready · notification.push   │
│  analytics.events                                   │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│ Data & Storage                                      │
│  PostgreSQL │ Redis │ MinIO (S3) │ Elasticsearch    │
│  Cloudflare CDN                                     │
└─────────────────────────────────────────────────────┘
```

---

### 4.2 Auth Flow (Keycloak + JWT)

```
Browser ──① login──→ Keycloak (Local / Google IdP)
        ←──② JWT────
        ──③ API + JWT──→ API Gateway
                         ──④ verify JWKS──→ Keycloak
                         ──forward──→ Core Services
                                      (nhận user_id, email, role từ JWT claims)

[Lần đầu đăng nhập] Keycloak event → User Service → Auto-create Channel
```

JWT Payload:
```json
{
  "sub": "keycloak_user_id",
  "email": "user@email.com",
  "roles": ["user"],
  "exp": 1234567890
}
```

---

### 4.3 Video Upload & Transcode Pipeline

**Phase 1 — Upload:**
```
Studio Site → POST /upload/init
            → tạo VIDEO (status = INIT)
            → tạo UPLOAD_SESSION (uploadId)
            → trả uploadId

Studio Site → Upload từng chunk:
            POST /upload/{uploadId}/chunk?index=1 (chunk ~10MB, resumable)
            → lưu MinIO: raw-videos/{uploadId}/chunk-{index}
            → DB: update UPLOAD_SESSION (uploaded_chunks / progress)

Studio Site → POST /upload/{uploadId}/complete
            → verify đủ chunk
            → merge chunk (service tự xử lý)
            → upload file hoàn chỉnh:
              raw-videos/{videoId}/original.mp4
            → (async) cleanup chunk cũ
            → DB: video.status = PROCESSING
            → DB: upload_session.status = COMPLETED
            → Kafka: publish video.uploaded { videoId, rawPath, resolutions }
```

**Phase 2 — Transcode:**
```
Kafka → Transcode Worker (Spring Boot + JavaCV/FFmpeg)
      → consume video.uploaded
      → pull file từ MinIO: raw-videos/{videoId}/original.mp4

      → 4 workers chạy song song:
        Worker 1: 1080p H.264 + HLS segments
        Worker 2: 720p H.264 + HLS segments
        Worker 3: 480p H.264 + HLS segments
        Worker 4: 360p H.264 + Thumbnail
```

**Phase 3 — Lưu trữ & Publish:**
```
MinIO bucket: processed-videos
  /videos/{videoId}/1080p/  master.m3u8 + segments
  /videos/{videoId}/720p/   ...
  /videos/{videoId}/480p/   ...
  /videos/{videoId}/360p/   ...
  /videos/{videoId}/thumbnail.jpg

Transcode Worker:
→ Kafka: publish video.ready { videoId, channelId, duration, thumbnailUrl }

Video Service (consumer):
→ DB: video.status = READY
→ DB: update metadata (duration, thumbnail_url)
→ In-app notify: Creator + Subscribers
```

---

### 4.4 Streaming Architecture

```
Browser (HLS.js) ──① metadata──→ Video Service (check Redis cache)
                 ←──② signed URL (master.m3u8, TTL 6h)──
                 ──③ fetch segments──→ Cloudflare CDN
                                        ── cache miss──→ MinIO origin

Heartbeat (mỗi 10s): POST position_ms → Watch History API
  → Write Redis ngay
  → Async flush → PostgreSQL (mỗi 30s)
  → Kafka: analytics.events
```

**HLS master.m3u8:**
```
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080 → 1080p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2800000,RESOLUTION=1280x720  → 720p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1400000,RESOLUTION=854x480   → 480p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360    → 360p/index.m3u8
```

---

### 4.5 Tech Stack (Final — sau khi update)

| Layer | Công nghệ | Ghi chú |
|---|---|---|
| Frontend | Next.js 14 (App Router) | SSR cho Viewing, CSR cho Studio |
| Video Player | HLS.js | Adaptive bitrate |
| **Backend** | **Java 21 + Spring Boot 3.x** | **Updated từ NestJS** |
| ORM | Spring Data JPA + QueryDSL | Flyway cho migration |
| Cache layer | Spring Data Redis | Tích hợp sẵn Spring |
| Auth | Spring Security OAuth2 Resource Server | Validate JWT qua JWKS |
| API Gateway | Nginx / Kong | Rate limit, JWT validation, routing |
| Auth Server | Keycloak 24+ | SSO, Google OAuth2, PKCE |
| Database | PostgreSQL 16 | Persistent data |
| Cache | Redis 7 | Metadata cache, watch position, view count buffer |
| Search | Elasticsearch 8 | Spring Data Elasticsearch |
| Storage | MinIO (S3-compatible) | AWS SDK for Java |
| CDN | Cloudflare | Edge cache HLS segments |
| **Queue** | **Apache Kafka** | **Updated từ RabbitMQ** |
| **Transcode** | **Spring Boot + JavaCV (FFmpeg binding)** | **Updated từ Node.js worker** |
| Infra | Docker + Docker Compose | Migrate sang K8s khi scale |

---

### 4.6 Repository Structure

```
videohub/
├── apps/
│   ├── studio/              # Next.js — Upload Site
│   ├── viewing/             # Next.js — Viewing Site
│   └── admin/               # Next.js — Admin Dashboard
│
├── services/                # Backend — Java Spring Boot
│   ├── api-gateway/         # Nginx / Kong config
│   ├── user-service/        # User, Channel
│   ├── video-service/       # Metadata, Upload (3-step chunked)
│   ├── stream-service/      # Watch history, Signed URL, HLS
│   ├── interaction-service/ # Like, Comment, Subscribe, Report
│   ├── notification-service/# In-app notify (Kafka consumer)
│   ├── search-service/      # Elasticsearch integration
│   ├── analytics-service/   # View count, watch time
│   └── transcode-worker/    # Kafka consumer + FFmpeg via JavaCV
│
├── infra/
│   ├── keycloak/            # Realm export, themes
│   ├── kafka/               # docker-compose kafka + zookeeper
│   ├── docker-compose.yml
│   └── nginx.conf
│
└── shared/
│   └── common-lib/          # Java library — shared DTOs, Kafka events
│       ├── build.gradle.kts
│       └── src/main/java/com/videohub/common/
```

```
video-service/
├── domain/
│   ├── model/          # Video, VideoFile (JPA Entities)
│   ├── event/          # VideoUploadedEvent, VideoReadyEvent
│   ├── repository/     # Interface — VideoRepository
│   └── exception/      # VideoNotFoundException, ...
├── application/
│   ├── usecase/        # InitUploadUseCase, CompleteUploadUseCase, ...
│   ├── dto/            # VideoDto, UploadInitDto, ...
│   └── port/           # StoragePort, KafkaPort (interfaces)
├── infrastructure/
│   ├── persistence/    # VideoJpaRepository, VideoMapper
│   ├── kafka/          # KafkaProducer, KafkaConsumer
│   ├── storage/        # MinioStorageAdapter
│   └── config/         # KafkaConfig, MinioConfig, SecurityConfig
└── presentation/
    ├── controller/     # VideoController
    ├── request/        # UploadInitRequest, ...
    └── response/       # VideoResponse, ...
```

---

## 5. API Contract

**Conventions:**
- Base URL: `https://api.videohub.com/api/v1/...`
- Auth: Bearer JWT từ Keycloak
- Pagination: `page`, `size`, `sort` — response: `content`, `totalElements`, `totalPages`
- Versioning: `/api/v1/` trong path
- Error format: `{ timestamp, status, error, message, path }`

---

### 5.1 User Service `/api/v1`

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | /users/me | JWT | Lấy profile user hiện tại |
| DELETE | /users/me | JWT | Xóa tài khoản (set isActive=false) |
| GET | /channels/{channelId} | Public | Xem thông tin kênh |
| GET | /channels/me | JWT | Kênh của mình (kể cả video private) |
| PUT | /channels/me | JWT | Cập nhật tên, mô tả, avatar kênh |
| POST | /channels/me/avatar | JWT | Upload avatar kênh |
| GET | /channels/{channelId}/videos | Public | Danh sách video public của kênh |

---

### 5.2 Video Service `/api/v1/videos`

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| POST | /videos/upload/init | JWT | Bước 1: Khởi tạo upload session → trả uploadId |
| POST | /videos/upload/{uploadId}/chunk | JWT | Bước 2: Upload từng chunk (resumable) |
| POST | /videos/upload/{uploadId}/complete | JWT | Bước 3: Hoàn tất → ghép file → publish Kafka |
| GET | /videos/{videoId} | Public* | Metadata video (*Private cần JWT + ownership) |
| PUT | /videos/{videoId} | JWT | Sửa title, desc, tags, visibility |
| POST | /videos/{videoId}/thumbnail | JWT | Upload thumbnail tùy chỉnh |
| DELETE | /videos/{videoId} | JWT | Xóa video + MinIO files |
| GET | /videos/me | JWT | Danh sách video của mình (Studio) |

---

### 5.3 Stream Service `/api/v1/stream`

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | /stream/{videoId}/manifest | Public* | Signed URL → master.m3u8 (TTL 6h) |
| POST | /stream/{videoId}/progress | JWT | Heartbeat lưu position_ms |
| GET | /stream/{videoId}/progress | JWT | Lấy vị trí xem cuối cùng |

---

### 5.4 Interaction Service `/api/v1`

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | /videos/{videoId}/likes | Public | Tổng like/dislike + reaction của user |
| PUT | /videos/{videoId}/reaction | JWT | Like hoặc Dislike (toggle) |
| GET | /videos/{videoId}/comments | Public | Danh sách top-level comments |
| POST | /videos/{videoId}/comments | JWT | Đăng comment mới |
| GET | /comments/{commentId}/replies | Public | Danh sách reply của comment |
| POST | /comments/{commentId}/replies | JWT | Reply vào comment (1 cấp) |
| DELETE | /comments/{commentId} | JWT | Xóa comment (creator hoặc tác giả) |
| POST | /videos/{videoId}/report | JWT | Báo cáo video vi phạm |
| PUT | /channels/{channelId}/subscribe | JWT | Subscribe/Unsubscribe (toggle) |
| GET | /channels/{channelId}/subscription | JWT | Kiểm tra trạng thái subscribe |

---

### 5.5 Notification Service `/api/v1/notifications`

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | /notifications | JWT | Danh sách notification (filter isRead) |
| GET | /notifications/unread-count | JWT | Số notification chưa đọc (badge) |
| PATCH | /notifications/{id}/read | JWT | Đánh dấu 1 notification đã đọc |
| PATCH | /notifications/read-all | JWT | Đánh dấu tất cả đã đọc |

---

### 5.6 Search Service `/api/v1/search`

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | /search/videos | Public | Tìm video theo keyword, tag, sort |
| GET | /search/channels | Public | Tìm kênh theo tên |
| GET | /search/tags/popular | Public | Danh sách tag phổ biến |

---

### 5.7 Analytics Service `/api/v1/analytics`

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | /analytics/videos/{videoId} | JWT (creator only) | Thống kê chi tiết video (views, watch time, likes) |
| GET | /analytics/channel/me | JWT | Tổng quan analytics toàn kênh |
| — | Kafka consumer: analytics.events | Internal | Nhận VIEW_START / VIEW_END events |

---

### 5.8 Admin Service `/api/v1/admin`

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | /admin/dashboard | Admin | Tổng quan hệ thống |
| GET | /admin/reports | Admin | Danh sách reports cần xử lý |
| PATCH | /admin/reports/{reportId} | Admin | Xử lý report (approve/reject) |
| PATCH | /admin/videos/{videoId}/visibility | Admin | Ẩn/khôi phục video |
| PATCH | /admin/users/{userId}/status | Admin | Khóa/mở khóa tài khoản |
| GET | /admin/users | Admin | Danh sách users + filter |

---

## 6. Kafka Topics

| Topic | Producer | Consumer | Payload |
|---|---|---|---|
| `video.uploaded` | video-service | transcode-worker | { videoId, rawPath, resolutions } |
| `video.ready` | transcode-worker | video-service, notification-service | { videoId, channelId } |
| `notification.push` | video-service, interaction-service | notification-service | { userId, type, content, refId } |
| `analytics.events` | stream-service | analytics-service | { type, videoId, userId?, durationMs } |

---