# QA Local Command Cheat Sheet

## 1) Script nhanh (khuyen dung)

Chay smoke QA local:

```powershell
.\scripts\qa-local-compose.ps1 -Action qa
```

Dung stack local:

```powershell
.\scripts\qa-local-compose.ps1 -Action up
```

Dung stack + build image truoc khi up:

```powershell
.\scripts\qa-local-compose.ps1 -Action up -Build
```

Build khong dung cache:

```powershell
.\scripts\qa-local-compose.ps1 -Action up -Build -NoCache
```

Xem service status:

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

Tat stack:

```powershell
.\scripts\qa-local-compose.ps1 -Action down
```

Chay kem edge-client:

```powershell
.\scripts\qa-local-compose.ps1 -Action qa -IncludeEdge
```

## 2) Docker Compose thu cong (neu khong dung script)

Up local stack:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Kiem tra service:

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

## 3) Quick health check

Backend health:

```powershell
Invoke-WebRequest http://localhost/api/health
```

Admin UI:

```powershell
Invoke-WebRequest http://localhost/admin/
```
