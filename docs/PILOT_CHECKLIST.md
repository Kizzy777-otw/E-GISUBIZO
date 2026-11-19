# Pilot and offline/low-bandwidth validation checklist

Use a staging deployment and test hardware/accounts only. Obtain informed consent, avoid collecting unnecessary household data, and stop any procedure that could expose a participant to gas, electrical, battery, height, or water hazards.

## Before each session

- [ ] Confirm the Vercel deployment is Preview/staging and uses the staging Neon branch, not Production.
- [ ] Confirm the deployment revision, current Alembic revision, active tree versions, and seeded test hardware.
- [ ] Check that Preview access is limited to the approved pilot group and expires/gets revoked on schedule.
- [ ] Verify household users do not receive technician/admin credentials.
- [ ] Verify technician account is active and restricted to the test district/sector.
- [ ] Record device model, browser, operating system, connection profile, and tree version; use anonymous test codes, not names/phone numbers.
- [ ] Measure the uncompressed app-shell plus active-tree payload. Automated tests enforce the 1 MB ceiling.

## Network and installation

- [ ] On a clean browser profile with a stable connection, open the portal, install the PWA if supported, and allow the service worker to finish installing.
- [ ] Validate one registered biogas contract (`HBGC-00001`) and one solar test unit while online; verify wrong model and unknown/legacy IDs are rejected.
- [ ] Confirm active diagnostic trees load and are stored in IndexedDB. Reload, then inspect that the offline mode still has the same tree version.
- [ ] Simulate 2G/3G: use browser DevTools throttling with high latency, low throughput, and intermittent request failures. Record first-load time, tree-load time, and failed requests.
- [ ] Repeat on an actual low-end Android device if available; DevTools throttling does not reproduce all device/storage constraints.

## Offline diagnosis and safety boundaries

- [ ] After a successful online hardware validation/tree download, enable airplane mode and reload the installed app.
- [ ] Start diagnosis for the previously validated unit. Confirm one question is shown at a time and no path presents more than three questions.
- [ ] Confirm an unvalidated/unknown unit cannot start an offline diagnosis.
- [ ] Exercise each seed-tree branch:
  - Biogas weak flame: water in line, acidic/overfeeding, inflated bag/obstruction, deflated bag/possible leak.
  - Solar red indicator: shaded/dirty panel, added high-draw appliance, flashing red LED, LED off.
- [ ] Verify advice does not ask participants to open gas lines/valves, search for leaks with flame, touch electrical wiring, open batteries, climb onto panels, or carry out work beyond the visible symptom. Stop and refer uncertain cases to a technician.
- [ ] For self-fix outcomes, record the recommended action and whether it was understood; do not ask participants to perform it if unsafe.
- [ ] For technician-required outcomes, inspect the displayed fault code and verify language remains probabilistic where evidence is incomplete (for example “possible obstruction/leak/controller fault”), not a definitive diagnosis.

## Queue, reconnect, and idempotency

- [ ] While offline, reach a technician-required outcome. Confirm the ticket and traversal path are stored locally, the pending count increments, and the household sees that it is queued.
- [ ] Close/reopen the PWA while still offline. Confirm the queue remains.
- [ ] Reconnect under throttled 2G/3G. Confirm automatic sync calls `POST /api/v1/tickets/sync`, tickets clear only after acknowledgement, and the server creates one ticket per client ticket ID.
- [ ] Simulate a lost response/retry. Confirm the repeat request returns `already_synced` rather than creating duplicate dispatch tickets.
- [ ] Leave more than 100 queued test tickets and reconnect; verify the client sends batches of no more than 100 and processes each acknowledged batch.
- [ ] Submit a malformed/rejected test ticket and confirm it remains locally visible with a useful rejection reason and does not prevent other valid batches from syncing.
- [ ] Verify the created ticket includes the exact diagnostic traversal and fault payload, is marked `requires_technician`, and generates one mock SMS audit event without sending an SMS.

## Technician workflow and authorization

- [ ] Confirm unauthenticated `GET /api/v1/tickets`, status mutation, and mock SMS trigger are rejected.
- [ ] Confirm a household/citizen has no route to technician data or mutation credentials.
- [ ] Sign in as a technician; verify queue visibility is limited to assigned district/sector and only tickets with `requires_technician` appear.
- [ ] Filter by each status (`Open`, `InProgress`, `Resolved`, `Closed`) and each priority; confirm closed items are visible when explicitly selected.
- [ ] Change a test ticket through status transitions. Confirm each update is recorded as an append-only audit event and does not alter its diagnostic path.
- [ ] Verify phone/contact data is not present in the ticket response, browser storage, or logs. If a future feature adds contact data, repeat an explicit role/privacy review before piloting it.
- [ ] Sign out and confirm protected ticket details disappear; revoke a test account and verify the next API request returns `401`.

## Session closeout

- [ ] Record completion, failures, user comprehension, self-fix vs. technician-needed outcome, sync latency, battery/network context, and safety concerns using anonymous session IDs.
- [ ] Do not put bearer tokens, Vercel bypass links, names, phone numbers, or connection strings in the field notes or issue tracker.
- [ ] Export only approved aggregate results; delete temporary participant/test records under the pilot data-retention policy.
- [ ] Revoke temporary Preview bypass access and test technician/admin tokens after the pilot.
- [ ] Triage any safety ambiguity before editing trees; have a qualified biogas/solar domain reviewer approve changes before publication.
