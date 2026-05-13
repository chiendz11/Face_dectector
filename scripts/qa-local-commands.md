# QA Local Commands (chi tiết)

## 1) Mặc định script chạy những gì?

Script `qa-local-compose.ps1` mặc định dùng 2 file:

- `docker-compose.yml`
- `docker-compose.dev.yml`

Nghĩa là chỉ chạy stack local chuẩn (backend, worker, frontend-admin, nginx, db, redis, minio...), chưa có edge-client.

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

## 4) Docker Compose thủ công (không dùng script)

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
docker compose -f docker-compose.yml -f docker-compose.dev.yml down --remove-orphans
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
