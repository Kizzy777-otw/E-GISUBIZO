# E-Gisubizo

An offline-first maintenance platform for rural biogas digesters and PAYGo solar systems. The citizen PWA downloads its decision trees for offline use, validates hardware against the registry before a diagnostic, and queues technician tickets in IndexedDB. The dispatch view is protected by bearer-token authentication.

## Requirements implemented from the SRS

- Kinyarwanda-first, icon-led diagnostic questions for biogas low flame and solar red battery/inverter indicators, with one question per screen and no more than three decision answers before a resolution or ticket.
- Registered hardware ID and model validation. A unit validated while online is remembered on that device for future offline diagnoses.
- Database-backed editable JSON trees, fault-code payloads, idempotent queued-ticket sync, technician status filtering, zone scoping, and append-only audit events.
- Mock SMS dispatch logging when a new ticket syncs; no live SMS gateway is contacted.
- Local PWA app-shell files and decision trees are small and have no third-party runtime assets. Measure the uncompressed cached shell with `Get-ChildItem frontend | Measure-Object -Property Length -Sum`; keep it below 1 MB when adding assets.

## Set up and run locally

### Requirements

- Git
- Python 3.12 (the required version is recorded in `.python-version`)

Clone the repository and change into its root directory:

```shell
git clone https://github.com/Kizzy777-otw/E-GISUBIZO.git
cd E-GISUBIZO
```

Create and activate a virtual environment, then install the project and its dependencies.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

macOS / Linux:

```shell
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

The app defaults to a local SQLite database (`egisubizo.db` in the current directory), so no database service is needed for a first run. Configure separate local admin and technician tokens before starting the server.

Windows PowerShell:

```powershell
$env:ADMIN_API_TOKEN = (python -c "import secrets; print(secrets.token_urlsafe(32))")
$env:TECHNICIAN_API_TOKEN = (python -c "import secrets; print(secrets.token_urlsafe(32))")
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

macOS / Linux:

```shell
export ADMIN_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export TECHNICIAN_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. On startup, the app creates the database tables, seeds the diagnostic trees and pilot hardware IDs `BIO-RW-0001` (biogas) and `SOL-RW-0001` (solar), and creates admin/technician accounts for any tokens supplied in the environment. The citizen PWA is at `/`, technician dispatch is at `/technician.html`, and administration is at `/admin.html`. Sign in with the corresponding token generated above. API documentation is available at `/docs`.

Optional configuration:

- `DATABASE_URL`: SQLAlchemy database URL. For local SQLite, leave it unset. To use PostgreSQL, install the declared `psycopg[binary]` dependency (included by `pip install -e .`) and use a `postgresql+psycopg://` URL.
- `TECHNICIAN_DISTRICT`: district assigned to the seeded technician account; defaults to `Rulindo`.
- `TECHNICIAN_SECTOR`: optional sector assigned to the seeded technician account; unset means no sector filter.
- `ALLOWED_ORIGINS`: comma-separated trusted origins, only needed when hosting the frontend separately. Same-origin deployments should leave it unset.

For a quick smoke check while the server is running:

```shell
curl http://127.0.0.1:8000/api/v1/diagnostic-trees
```

Stop the local server with `Ctrl+C`. The generated SQLite database contains local development data and should not be used as a production database.

## Run backend tests

Install the optional test dependencies into the active virtual environment, then run the test suite from the repository root:

```shell
python -m pip install -e ".[test]"
python -m pytest
```

The API tests use an isolated temporary SQLite database and seeded test-only credentials; they do not connect to Neon or a deployed environment.

## Free pilot deployment (Vercel Hobby + Neon Free)

This deployment targets **pilot/testing use**, not production-critical data. Vercel Hobby includes hosted HTTPS and Python FastAPI functions; Neon Free supplies PostgreSQL. Both plans have usage and recovery limitations, and the database can scale to zero after inactivity, adding a cold start. A free-tier deployment does not provide production-grade availability or recovery guarantees. Check Vercel's current Hobby terms and limits before inviting a wider audience.

1. Create a **Neon Free** PostgreSQL project. Choose a region near the users and copy its pooled connection string. The Vercel `app` service publishes the files in `frontend/`; the `backend` service runs FastAPI from the repository root using the dependencies in `pyproject.toml` and Python version in `.python-version`.
2. Import this GitHub repository into a Vercel Hobby project with the repository root as the project root. `vercel.json` configures the `app` and `backend` services and routes `/api/*` to FastAPI while serving other paths from the frontend. The browser uses same-origin `/api/v1` requests, so no service binding is needed. Add the environment variables in the next step before the first production deployment.
3. In **Project → Settings → Environment Variables**, set the Production variables:
   - `APP_ENV` = `production`
   - `DATABASE_URL` = Neon connection string, with the scheme changed from `postgresql://` to `postgresql+psycopg://` and `sslmode=require` enabled.
   - `ADMIN_API_TOKEN` = a unique, long random administrator token.
   - `TECHNICIAN_API_TOKEN` = a different, unique technician token.
   - `TECHNICIAN_DISTRICT` = the initial technician district, for example `Rulindo`.
   - `TECHNICIAN_SECTOR` = optional technician sector, for example `Base`.
   Keep credentials in Vercel's environment-variable settings; never put them in Git or chat.
4. Redeploy after setting the variables. Open the Vercel HTTPS domain and verify `/`, `/technician.html`, and `/admin.html`. Sign in to the admin page to register the pilot hardware and create individual technician accounts.
5. Monitor Vercel and Neon usage, export the Neon database regularly, and test a database restore before storing real household records. Free-tier usage can be capped or changed by the providers. Upgrade to paid compute and a database plan with managed backups before relying on the service for production maintenance.

### Staging and pilot readiness

- Staging is deployed at [the Vercel Preview URL](https://e-gisubizo-fiokbp13l-kizzy777-otw.vercel.app/). Preview uses a separate Neon `staging` schema-only branch; it does not copy production records. Its `DATABASE_URL`, `APP_ENV`, `ADMIN_API_TOKEN`, and `TECHNICIAN_API_TOKEN` are configured as Vercel Preview variables, separate from Production.
- Vercel Deployment Protection currently requires Vercel authentication to open the Preview URL. Keep it protected unless access is deliberately arranged for pilot participants.
- The ignored local file `.env.staging.local` contains the staging credentials for local reference. Never commit or share it. The production credentials remain in `.env.production.local`.
- The staging API has been checked with both pilot units: `BIO-RW-0001` / `biogas` and `SOL-RW-0001` / `solar`.
- **Field pilot validation is still outstanding.** Test with consenting rural households and technicians, including low-bandwidth and offline diagnosis, hardware registration, ticket queuing and sync, and dispatch updates. Record comprehension, diagnostic accuracy, and safety feedback before revising Kinyarwanda wording or decision trees.
- **Production-grade operations are still outstanding.** The current free-tier deployment is for pilot/testing, not production-critical use. Before a wider rollout, select plans that meet availability and backup requirements, configure and test database backups/restores, and confirm the registered hardware inventory and operational monitoring.

Production mode refuses to start with SQLite because function filesystems are not persistent. Do not send access tokens or database connection strings in chat.

## Production and administration

- Use the hosting platform's HTTPS/TLS endpoint in production; the development Uvicorn command above is intentionally local HTTP. For a self-hosted deployment, terminate TLS at a trusted reverse proxy.
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
