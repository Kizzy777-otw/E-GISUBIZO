# E-Gisubizo

An offline-first maintenance platform for rural biogas digesters and PAYGo solar systems. The citizen PWA downloads its decision trees for offline use, validates hardware against the registry before a diagnostic, and queues technician tickets in IndexedDB. The dispatch view is protected by bearer-token authentication.

## Requirements implemented from the SRS

- Kinyarwanda-first, icon-led diagnostic questions for biogas low flame and solar red battery/inverter indicators, with one question per screen and no more than three decision answers before a resolution or ticket.
- Registered hardware ID and model validation. A unit validated while online is remembered on that device for future offline diagnoses.
- Database-backed editable JSON trees, fault-code payloads, idempotent queued-ticket sync, technician status filtering, zone scoping, and append-only audit events.
- Mock SMS dispatch logging when a new ticket syncs; no live SMS gateway is contacted.
- Local PWA app-shell files and decision trees are small and have no third-party runtime assets. Measure the uncompressed cached shell with `Get-ChildItem frontend | Measure-Object -Property Length -Sum`; keep it below 1 MB when adding assets.

## Run locally

Use Python 3.10 or later. From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
$env:TECHNICIAN_API_TOKEN = "replace-with-a-long-random-technician-token"
$env:ADMIN_API_TOKEN = "replace-with-a-long-random-admin-token"
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. The service initializes a local SQLite database and two pilot hardware IDs: `BIO-RW-0001` and `SOL-RW-0001`. The technician table is at `/technician.html`; sign in with the configured technician token. Set `TECHNICIAN_DISTRICT` and optionally `TECHNICIAN_SECTOR` to limit the technician's queue. The seeded pilot units are in Rulindo / Base.

`DATABASE_URL` can be set to a SQLAlchemy SQLite or PostgreSQL URL. For PostgreSQL, install the declared `psycopg[binary]` dependency. `ALLOWED_ORIGINS` is a comma-separated list and should only be set to trusted origins when hosting the frontend separately.

## Production and administration

- Terminate TLS 1.3 at a trusted reverse proxy and forward only HTTPS traffic in production. The development Uvicorn command above is intentionally local HTTP.
- Set long, unique `TECHNICIAN_API_TOKEN` and `ADMIN_API_TOKEN` secrets. Only SHA-256 token hashes are persisted. Do not expose tokens in URLs or store technician tokens beyond the current browser session.
- Configure a durable database, backups, monitoring, and restricted CORS origins before deployment. Live SMS, USSD, and telemetry integrations are out of scope.
- An administrator can register a unit with `POST /api/v1/hardware` and update an existing tree with `PUT /api/v1/diagnostic-trees/{slug}` using `Authorization: Bearer <ADMIN_API_TOKEN>`. API docs are available at `/docs`.
- The administrator web view at `/admin.html` provides a sign-in, hardware registration form, and JSON decision-tree editor.
- Administrators can issue technician/admin accounts and revoke or restore access at `/api/v1/users`; newly issued bearer tokens are shown once in the admin view and must be copied securely.
- Citizen offline mode can validate only hardware already validated online on that same browser. Unknown hardware cannot safely pass registry validation without a connection.

## API overview

- `POST /api/v1/hardware/validate`
- `GET /api/v1/diagnostic-trees`
- `POST /api/v1/tickets/sync`
- `GET /api/v1/tickets?status=Open&priority=High` (technician/admin token)
- `PATCH /api/v1/tickets/{ticket_id}/status` (technician/admin token)
- `POST /api/v1/notifications/sms-trigger` (technician/admin token; mock only)
- `GET|POST /api/v1/users` and `PATCH /api/v1/users/{id}/access` (admin token)

The service-worker cache contains only the local app shell; trees and previously validated hardware are stored in IndexedDB. Queued ticket records are deleted only after an acknowledged sync. Each ticket's diagnostic path is saved at creation and never updated; subsequent status changes append audit records.
