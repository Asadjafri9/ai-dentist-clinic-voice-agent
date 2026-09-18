# Operations Runbook

## Services

| Component | Location | Notes |
|-----------|----------|-------|
| API + worker | Railway `ai-dentist-voice-agent-api` (project `exemplary-radiance`, svc `dbd1bdc7-…`) | `backend/start.sh` runs worker + uvicorn; auto-deploys on push to `main` |
| Dashboard | Vercel `ai-dentist-clinic-voice-agent` | auto-deploys on push to `main` |
| MongoDB | Atlas project `ai-voice-agent`, `Cluster0` | user `ai_voice_agent` |
| Telephony | Vapi phone `+1 661 463 3323`, assistant `b7f88433-…` | server URL w/ HMAC credential `7cda4ec2-…` |

Railway service config: `rootDirectory=backend`, build installs via
`backend/requirements.txt` (`-e .`), start command `sh start.sh`, healthcheck
`/api/v1/health/live`. Manage with `railway` CLI (`serviceInstanceUpdate`
GraphQL mutation for settings, `railway variable set` for env vars).

## Smoke test (after any deploy)

```bash
API=https://ai-dentist-voice-agent-api-production.up.railway.app
curl -s $API/api/v1/health/live                    # {"status":"live"}
curl -s $API/api/v1/health/ready                   # all checks true
curl -s -X POST $API/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<admin>","password":"<pw>"}'       # 200 + session cookie
# signed Vapi webhook round-trip: see backend/tests or scripts in git history
```

Dashboard: open the Vercel URL, log in, confirm calls/appointments lists load.

## Common failures

### `/health/ready` shows `worker: false`
Worker heartbeat is stale (>10 min). On Railway the worker shares the API container —
check `railway logs -s ai-dentist-voice-agent-api` for `worker_started`
and `worker_loop_error`. Restart the service if missing.

### Jobs dead-lettered
`db.jobs.find({status:"dead"})` — inspect `last_error_code`. Fix the cause, then requeue
by setting `status:"pending"`, `available_at` to now, `attempts:0`.

### Vapi webhook 401s
Signature mismatch. Verify the Vapi custom credential still exists and its `secretKey`
equals `VAPI_SERVER_CREDENTIAL_SECRET` on Railway. Timestamp skew limit is 300s.

### Bookings return TEMPORARY_FAILURE
Usually Mongo write contention or connectivity. Transient `WriteConflict` retries are
bounded; check API logs for `book_appointment_unexpected`. Losers correctly receive
`SLOT_UNAVAILABLE` — that is not an error.

### Login works locally but not on Vercel
Cross-site cookies need `AUTH_COOKIE_SAMESITE=none` + `AUTH_COOKIE_SECURE=true` on Railway
and the exact Vercel origin in `FRONTEND_ORIGINS`.

## Rotating secrets

1. `VAPI_SERVER_CREDENTIAL_SECRET`: set new value on Railway, create a new Vapi
   `custom-credential` (HMAC, sha256, `x-signature`/`x-timestamp`), update the assistant's
   `server.credentialId`, then update `businesses.vapi_server_credential_id`.
2. `AUTH_CSRF_SECRET` / `OFFER_TOKEN_SECRET`: rotate on Railway; in-flight offer tokens and
   CSRF cookies invalidate (callers re-request slots; users re-login on next mutation).
3. `MONGODB_URI`: update password in Atlas (`atlas dbusers`), then env var on Railway.

## Seeding a new clinic

```bash
SEED_ADMIN_EMAIL=… SEED_ADMIN_PASSWORD=… MONGODB_URI=… seed-demo
```
Then set `vapi_phone_number_id` / `vapi_assistant_id` on the business doc so inbound calls
resolve to the tenant.

## Retention

`TRANSCRIPT_RETENTION_DAYS` (default 30). The worker schedules `retention_purge` hourly;
it deletes transcript bodies older than the window while keeping call metadata.
