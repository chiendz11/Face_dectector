# QA Local Commands (chi tiết)

## 1) Mặc định script chạy những gì?

Script `qa-local-compose.ps1` mặc định dùng 2 file:

- `docker-compose.yml`
- `docker-compose.dev.yml`

Nghĩa là chạy stack local chuẩn (backend, worker, frontend-admin,
nginx, db, redis, minio...), chưa có edge-client.

## 2) Khi nào edge-client được chạy?

Edge-client chỉ được thêm khi có cờ `-IncludeEdge`.

Ví dụ chạy QA có edge-client:

```powershell
.\scripts\qa-local-compose.ps1 -Action qa -IncludeEdge
```

Ví dụ up stack có edge-client:

```powershell
.\scripts\qa-local-compose.ps1 -Action up -IncludeEdge
```

Bạn không cần mở thêm cửa sổ để chạy edge-client riêng nếu đã dùng `-IncludeEdge` (vì edge-client chạy bằng container từ `docker-compose.edge.yml`).

## 3) Bộ lệnh khuyến nghị (dùng script)

Chạy smoke QA local:

```powershell
.\scripts\qa-local-compose.ps1 -Action qa
```

Chạy smoke QA local và build image trước khi test:

```powershell
.\scripts\qa-local-compose.ps1 -Action qa -Build
```

Chạy smoke QA local và build lại sạch (không cache):

```powershell
.\scripts\qa-local-compose.ps1 -Action qa -Build -NoCache
```

Chạy smoke QA local + edge-client:

```powershell
.\scripts\qa-local-compose.ps1 -Action qa -IncludeEdge
```

Up local stack:

```powershell
.\scripts\qa-local-compose.ps1 -Action up
```

Up local stack và build image trước:

```powershell
.\scripts\qa-local-compose.ps1 -Action up -Build
```

Build không dùng cache:

```powershell
.\scripts\qa-local-compose.ps1 -Action up -Build -NoCache
```

Xem trạng thái service:

```powershell
.\scripts\qa-local-compose.ps1 -Action ps
```

Xem log:

```powershell
.\scripts\qa-local-compose.ps1 -Action logs
```

Xem log realtime:

```powershell
.\scripts\qa-local-compose.ps1 -Action logs -Follow
```

Restart stack:

```powershell
.\scripts\qa-local-compose.ps1 -Action restart
```

Tắt stack:

```powershell
.\scripts\qa-local-compose.ps1 -Action down
```


## 4) Chạy edge-client: local vs container

### a) Chạy edge-client trực tiếp trên máy tính (không container)

Yêu cầu: đã cài Python và dùng venv riêng cho `edge-client`. Không dùng chung root `.venv` của repo nếu venv đó đã cài security tooling như `semgrep` hoặc `pip-audit`, vì tooling có thể kéo dependency mâu thuẫn với runtime app.

```powershell
# (Từ thư mục gốc repo)
cd edge-client

# Nếu đang kích hoạt root .venv chung của repo, thoát trước:
if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }

# Tạo venv riêng cho edge-client. Dùng py -3.13 nếu máy local không có Python 3.11.
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Cài dependencies:
# (Tùy chọn) .\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check

# Test giao diện/camera khi chưa bật backend:
$env:EDGE_BACKEND_ENABLED = "true"
$env:EDGE_UI_MODE = "web"
$env:EDGE_KIOSK_PORT = "8080"  # Dùng 8081 nếu container edge-client đang chiếm 8080.

# Chạy edge-client qua compatibility launcher
.\.venv\Scripts\python.exe main.py
```

Mở kiosk UI ở:

```text
http://localhost:8080
```

Nếu cần chạy legacy OpenCV window thay vì web kiosk:

```powershell
$env:EDGE_UI_MODE = "opencv"
.\.venv\Scripts\python.exe main.py
```

Nếu muốn chạy entrypoint package sau khi refactor:
```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m edge_client
```

### b) Chạy edge-client trong container (docker compose)

Edge-client sẽ được up cùng stack khi dùng compose với file `docker-compose.edge.yml`:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.edge.yml up -d --build
```

Hoặc với script:
```powershell
./scripts/qa-local-compose.ps1 -Action up -IncludeEdge
```

Để chỉ restart edge-client container:
```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.edge.yml restart edge-client
```

Để xem log edge-client:
```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.edge.yml logs -f edge-client
```

## 5) Health check đúng endpoint

Up local stack:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Up local stack + edge-client:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.edge.yml up -d --build
```

Kiểm tra service:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
```

Xem log:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f
```

Down local stack:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.edge.yml down --remove-orphans
```


## 5) Health check đúng endpoint

Backend root health qua nginx:

```powershell
Invoke-WebRequest http://localhost/health
```

Admin API health:

```powershell
Invoke-WebRequest http://localhost/api/admin/health
```

Admin UI:

```powershell
Invoke-WebRequest http://localhost/admin/
```

Enrollment compatibility redirect:

```powershell
Invoke-WebRequest http://localhost/admin/
```

## 6) Troubleshooting khi `-Action qa` bị timeout

Nếu script báo timeout ở `http://localhost/health`, nguyên nhân thường là backend chưa start thành công dù container đang `Up`.

Quy trình kiểm tra nhanh:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs backend --tail 100
```

Lỗi hay gặp: backend văng do mismatch dependency (ví dụ `numpy` và `opencv-python`).

Khi gặp trường hợp này, ưu tiên build lại image rồi chạy QA:

```powershell
.\scripts\qa-local-compose.ps1 -Action qa -Build
```

Nếu vẫn lỗi, build sạch:

```powershell
.\scripts\qa-local-compose.ps1 -Action qa -Build -NoCache
```

## 7) Manual E2E: enroll face rồi verify qua edge

Flow này dùng frontend-admin để tạo vector thật trong Postgres/pgvector, sau đó
edge-client gửi face crop về backend để verify.

Trước khi chạy, đảm bảo file `.env` local đang dùng cùng model contract với
`.env.example`:

```env
EMBEDDING_PROVIDER=deepface
MODEL_NAME=Facenet512
MODEL_VERSION=2026.05-deepface-facenet512
EMBEDDING_DIMENSIONS=512
DEEPFACE_DETECTOR_BACKEND=opencv
DEEPFACE_ALIGN=true
DEEPFACE_ENFORCE_DETECTION=false
EMBEDDING_ALLOW_HASH_FALLBACK=false
MATCH_THRESHOLD=0.55
```

Chạy stack server:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Chạy migration. Migration đổi `face_embeddings.embedding` sang `vector(512)` sẽ
fail nếu bảng đã có embedding cũ; khi local test chưa có dữ liệu, migration sẽ
đi qua bình thường.

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend alembic upgrade head
```

Mở admin UI:

```text
http://localhost/admin/
```

Mở admin enrollment session UI:

```text
http://localhost/admin/
```

Lưu ý production: admin enrollment session phải chạy qua HTTPS để browser cho phép
truy cập camera. `localhost` chỉ là ngoại lệ cho dev/test local.

Login bằng user/password trong `.env`, tạo employee ở admin UI, rồi dùng
admin enrollment session để chụp 3-5 mẫu mặt live cho employee đó.

Kiểm tra vector đã được ghi:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec db psql -U postgres -d face_detector -c "select employee_code, created_at from face_embeddings;"
```

Test API recognition bằng ảnh file:

```powershell
curl.exe -F "device_name=local-manual-test" -F "file=@.\path\to\face.jpg" http://localhost/api/vision/recognize
```

Trên Windows, chạy edge-client bằng venv local để verify ở kiosk:

```powershell
cd edge-client
.\.venv\Scripts\Activate.ps1
$env:API_BASE_URL = "http://localhost"
$env:EDGE_BACKEND_ENABLED = "true"
$env:EDGE_UI_MODE = "web"
python main.py
```

Mở kiosk UI:

```text
http://localhost:8080
```
