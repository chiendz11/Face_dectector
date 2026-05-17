# Enrollment Station

Local web app for controlled face enrollment.

The station is separate from `edge-client` so production verification at the
gate cannot accidentally create or overwrite employee face templates.

## Local Development

```powershell
cd enrollment-station
npm install
npm run dev
```

Open:

```text
http://localhost:5174/enroll/
```

The app expects the backend API through `/api`, either via Vite proxy in dev or
via the repository Nginx route in Docker Compose.

For production, serve the station over HTTPS. Browser camera APIs are only
available in secure contexts, except for `localhost` during development.
