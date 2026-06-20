Tóm tắt Session — VideoHub Backend Scaffold
Rules m phải follow (từ prompt của bạn)

Chỉ đưa ra ONE step tại một thời điểm
Mỗi step phải nhỏ và actionable (tạo file X, chạy lệnh Y)
Không generate full implementation
Không generate large code blocks trừ khi thực sự cần thiết
Chờ confirm trước khi sang step tiếp theo
Ưu tiên commands, structure, short snippets thay vì full code


Context

Project: VideoHub (YouTube-like platform)
Backend: Java 21 + Spring Boot 3.x
Architecture: Microservices — tổ chức theo Monorepo
Build tool: Gradle multi-module
Queue: Kafka
Internal package structure: DDD / Clean Architecture (đã confirm ở cuối session)
Modules đã define sẵn — không cần redesign


Goal
Scaffold project structure step-by-step — folders, Gradle config, first service skeleton.

Các Step đã hoàn thành
Step 1 Tạo thư mục gốc videohub/, init git, tạo .gitignore
Step 2 Tạo settings.gradle.kts — khai báo tất cả modules
Step 3 Tạo gradle/libs.versions.toml — Version Catalog
Step 4 Tạo root build.gradle.kts — common config cho tất cả submodules
Step 5 Tạo Gradle Wrapper (gradlew, gradlew.bat, gradle-wrapper.properties)
Step 6 Tạo folder structure cho video-service (Maven standard layout)
Step 7 Tạo build.gradle.kts riêng cho video-service
Step 8 Tạo VideoServiceApplication.java + application.yml
Step 9 Tạo shared:common-lib — folder structure + build.gradle.kts
Step 10 Tạo package structure theo DDD cho video-service
	video-service/
		└── src/main/java/com/videohub/video/
		    ├── domain/           # Entities, Value Objects, Domain Events
		    ├── application/      # Use Cases, DTOs, Ports (interfaces)
		    ├── infrastructure/   # JPA, Kafka, MinIO, Redis implementations
		    ├── presentation/     # REST Controllers, Request/Response
		    └── VideoServiceApplication.java
Step 11 Tạo sub-packages bên trong từng layer
	# domain layer
	mkdir -p services/video-service/src/main/java/com/videohub/video/domain/model
	mkdir -p services/video-service/src/main/java/com/videohub/video/domain/event
	mkdir -p services/video-service/src/main/java/com/videohub/video/domain/repository
	mkdir -p services/video-service/src/main/java/com/videohub/video/domain/exception

	# application layer
	mkdir -p services/video-service/src/main/java/com/videohub/video/application/usecase
	mkdir -p services/video-service/src/main/java/com/videohub/video/application/dto
	mkdir -p services/video-service/src/main/java/com/videohub/video/application/port

	# infrastructure layer
	mkdir -p services/video-service/src/main/java/com/videohub/video/infrastructure/persistence
	mkdir -p services/video-service/src/main/java/com/videohub/video/infrastructure/kafka
	mkdir -p services/video-service/src/main/java/com/videohub/video/infrastructure/storage
	mkdir -p services/video-service/src/main/java/com/videohub/video/infrastructure/config

	# presentation layer
	mkdir -p services/video-service/src/main/java/com/videohub/video/presentation/controller
	mkdir -p services/video-service/src/main/java/com/videohub/video/presentation/request
	mkdir -p services/video-service/src/main/java/com/videohub/video/presentation/response
Step 12 Tạo docker-compose.yml cho local infrastructure
	services:

	  postgres:
	    image: postgres:16-alpine
	    container_name: videohub-postgres
	    environment:
	      POSTGRES_DB: videohub
	      POSTGRES_USER: videohub
	      POSTGRES_PASSWORD: videohub
	    ports:
	      - "5432:5432"
	    volumes:
	      - postgres_data:/var/lib/postgresql/data

	  redis:
	    image: redis:7-alpine
	    container_name: videohub-redis
	    ports:
	      - "6379:6379"

	  zookeeper:
	    image: confluentinc/cp-zookeeper:7.6.0
	    container_name: videohub-zookeeper
	    environment:
	      ZOOKEEPER_CLIENT_PORT: 2181

	  kafka:
	    image: confluentinc/cp-kafka:7.6.0
	    container_name: videohub-kafka
	    depends_on:
	      - zookeeper
	    ports:
	      - "9092:9092"
	    environment:
	      KAFKA_BROKER_ID: 1
	      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
	      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
	      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

	  minio:
	    image: minio/minio:latest
	    container_name: videohub-minio
	    command: server /data --console-address ":9001"
	    ports:
	      - "9000:9000"
	      - "9001:9001"
	    environment:
	      MINIO_ROOT_USER: videohub
	      MINIO_ROOT_PASSWORD: videohub123
	    volumes:
	      - minio_data:/data

	volumes:
	  postgres_data:
	  minio_data:
Step 13 Cập nhật application.yml cho video-service
Step 14 Tạo Flyway migration file đầu tiên services/video-service/src/main/resources/db/migration/V1__create_video_tables.sql

Quyết định quan trọng đã confirm

Monorepo — tất cả services trong 1 repo
DDD / Clean Architecture bên trong mỗi service với 4 layers: domain · application · infrastructure · presentation
Không dùng Layered Architecture