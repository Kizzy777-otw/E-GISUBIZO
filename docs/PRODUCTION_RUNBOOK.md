# Database operations and production runbook

The separate Free Neon project `e-gisubizo-pilot` (`fragrant-math-02674688`, `aws-eu-central-1`) was created for non-critical pilot/staging use, and its initial migration and seed data have been applied. It is not a production database. Vercel environment variables and deployment protection have not been changed. The production project remains a separate future operator decision.

## Environment isolation

Keep three different databases/branches and credentials:

| Environment | `APP_ENV` | Database | Runtime `DATABASE_URL` |
| --- | --- | --- | --- |
| Local/tests | `development` / `test` | Local SQLite or isolated test SQLite | Never production |
| Vercel Preview | `staging` | Neon `e-gisubizo-pilot` project, `main` branch | Pooled pilot URL |
| Vercel Production | `production` | Dedicated production Neon project/branch | Pooled production URL |

Set `ADMIN_API_TOKEN` and `TECHNICIAN_API_TOKEN` independently for Preview and Production. Do not copy production credentials or data into Preview. Keep `ALLOWED_ORIGINS` unset for same-origin Vercel routing; when hosting the frontend elsewhere, list only its exact HTTPS origins. Never use `*`.

Vercel's `/api/(.*)` rewrite sends API requests to FastAPI; `/docs`, `/openapi.json`, and `/redoc` also go to FastAPI, and the final rewrite serves frontend assets. Keep the citizen PWA and API on the same origin so browser requests and service-worker scope remain same-origin. `/sw.js` must remain `no-cache` so clients can discover app-shell updates.
`/healthz` is routed to FastAPI and checks that the configured database accepts a query; monitor it as a dependency-health check, not as proof that the full pilot flow works.

## Preview access for invited field testing

1. Keep Vercel Deployment Protection enabled for Preview. Grant the pilot coordinator access or configure a short-lived Preview protection bypass for the specific deployment, using Vercel's supported controls.
2. Share a bypass link/token only with named pilot coordinators through an approved private channel. Set an expiry where supported and revoke/rotate it after the pilot. Do not place it in this repository, the PWA, issue text, or a public QR code.
3. Keep technician and administrator bearer tokens separate from the Preview bypass. A bypass opens the deployment; it must not replace API role authorization.
4. Provision individual technician accounts with zone assignments through the admin page. Give households only the public citizen portal, and do not give them admin/technician tokens.
5. Test the bypass using a private browser and a low-bandwidth profile. Verify `/`, `/api/v1/diagnostic-trees`, and `/technician.html`; the dispatch data must still require a technician/admin bearer token.
6. If the Vercel plan/account cannot provide controlled Preview access to external pilot participants, use an explicitly approved pilot deployment/access mechanism rather than disabling protection on all previews.

## Migration and release procedure

The application runtime uses a pooled PostgreSQL URL. Alembic uses a **direct, non-pooled** URL and is not run by a Vercel function cold start. `DB_AUTO_CREATE` is intentionally rejected when enabled on Vercel or in staging/production.

### New, empty production database

1. Create/approve the dedicated production Neon project and branch in the correct region. Confirm retention/history-window and plan requirements with the operations owner.
2. Put the **pooled production** URL in Vercel Production as `DATABASE_URL`; use the SQLAlchemy `postgresql+psycopg://` scheme and Neon TLS query parameters from the provider. Set `APP_ENV=production`.
3. In a controlled release environment, set `DATABASE_MIGRATION_URL` to the **direct** production URL (without `-pooler`) and run:

   ```powershell
   python -m alembic upgrade head
   python -m backend.seed
   ```

   Run this only after reviewing the target URL and confirming a recovery point exists. Do not print the URL in CI logs or commit it.
4. Verify `alembic current`, the seeded diagnostic trees and hardware, and authenticated/unauthenticated API behavior using the production HTTPS origin. Only then deploy/promote the application.
5. Record the deployed Git revision, Alembic revision, operator, and timestamp in the release log.

### Existing staging database

Do not run `upgrade head` against a database whose schema was created by `create_all` until its schema has been compared with the initial migration. Back it up first. If it exactly matches, a database owner may baseline it with `python -m alembic stamp 0001_initial`; otherwise plan an explicit reconciliation migration on a disposable Neon branch first. Then seed with `python -m backend.seed` and verify the Preview URL before pilot use.

For all future schema changes: create a new Alembic revision, inspect its SQL, apply it to a disposable branch, run tests and API smoke checks, take/confirm a recoverable production point, apply through the controlled direct-URL migration step, then deploy code. Never use `Base.metadata.create_all()` as a production upgrade mechanism.

## Recovery, backups, and monitoring

- In Neon, choose and periodically review a history window that meets the agreed recovery-point and recovery-time objectives. Neon's instant restore / branch-from-past capability only reaches within the configured retained history window; retention and cost depend on the plan. Consult [Neon branching and restore](https://neon.com/docs/introduction/branching.md) and [instant restore](https://neon.com/docs/postgres/backup-restore/branch-restore.md).
- The current pilot project is on Neon Free: instant-restore history is capped at 6 hours (up to 1 GB of changes), there is one manual snapshot, monitoring retention is one day, and there is no uptime SLA. Treat it as non-critical pilot infrastructure only. See [Neon plan details](https://neon.com/docs/introduction/plans.md) and [history-window limits](https://neon.com/docs/postgres/backup-restore/history-window.md).
- Before risky releases, create a named recovery branch/snapshot from the production branch using the Neon Console or approved CLI workflow. Keep it access-restricted and document when it can be deleted.
- Maintain an encrypted off-project logical backup on an approved schedule if the recovery objective requires protection beyond Neon history. Use the direct URL for `pg_dump`; encrypt at rest, restrict access, and record retention. Never back up production into a Preview branch.
- At least quarterly, restore a recent point to an isolated branch/database, run `alembic current`, verify tree/hardware/ticket/audit counts and a read-only API smoke test, and record measured recovery time. Do not test restoration by overwriting production.
- Alert on sustained API 5xx rates, failed health checks, sync rejection/error spikes, database connection saturation, elevated latency, and failed/aged deployments. Route alerts to a monitored owner and document escalation.
- Review Vercel function logs and Neon query/connection/compute monitoring after each pilot session. Avoid logging bearer tokens, phone numbers, or unnecessary household identifiers. The current mock SMS logs ticket, hardware and zone identifiers but does not send an SMS or record a phone number.

### Health and release smoke checks

```shell
curl -fsS https://<deployment-host>/api/v1/diagnostic-trees
curl -fsS https://<deployment-host>/healthz
curl -sS -o /dev/null -w "%{http_code}\n" https://<deployment-host>/api/v1/tickets
```

The first request should return the active tree JSON. The unauthenticated ticket request should return `401`. Also exercise a staging-only hardware validation, ticket sync, technician status update, and mock SMS trigger with test records and the appropriate role; never create test tickets in production without approval.

## Known operational limits

- The API currently exposes no household phone-number field. The `MOCK_SMS_TRIGGERED` event is an audit/log action only; integrating a real provider requires a separate privacy, consent, delivery, and secret-management review.
- Vercel Preview wiring/protection changes, production project provisioning, backup retention selection, and production migrations remain operator-controlled actions.
- Staging and test must remain isolated from Production at both database URL and credentials. Tests use a temporary SQLite database.
