# AI Dentist Clinic Voice Agent

AI voice receptionist for dental clinics: answers inbound calls, answers configured clinic
questions, and books appointments against real, transactionally-safe availability. Includes
a clinic admin dashboard for calls, appointments, patients, services, providers, and
availability management.

Booking correctness is prioritized over conversational cleverness: the voice agent can only
confirm an appointment after the backend commits it inside a MongoDB transaction.

## Architecture

```
Inbound call (Vapi phone number)
  -> Vapi assistant (system prompt generated from clinic config)
  -> POST /api/v1/integrations/vapi/server   (HMAC-signed, replay-protected)
       -> tenant resolved server-side from phone_number_id / assistant_id
       -> tools: get_clinic_info, get_services, get_available_slots, book_appointment
       -> book_appointment validates a signed offer token + caller confirmation
          and commits inside a MongoDB transaction (schedule-day concurrency guard)
  -> end-of-call-report enqueues durable job -> worker derives outcome,
     stores call record + transcript (retention-limited)
Dashboard (Next.js) -> session cookie + CSRF -> tenant-scoped admin APIs
```

- `backend/` — FastAPI + PyMongo async. Business logic in `app/services`, data access in
  `app/repositories`, provider-specific payloads isolated in `app/integrations/vapi`,
  durable async work in `app/workers`.
- `frontend/` — Next.js 15 + Tailwind dashboard (`/dashboard/*`).
- `plans/PRD.md` — product requirements this implements.

## Local setup

### Backend

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in MONGODB_URI + secrets
uvicorn app.main:app --port 8000
```

Worker (durable jobs: post-call processing, retention purge, assistant sync):

```bash
python -m app.workers.runner          # loop mode
python -m app.workers.runner --once   # drain pending jobs and exit (cron)
```

Seed demo data (fictional BrightSmile Dental clinic, services, providers, schedules):

```bash
SEED_ADMIN_EMAIL=admin@brightsmile-demo.com SEED_ADMIN_PASSWORD=<pick-one> seed-demo
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev -- --port 3000
```

Login at `http://localhost:3000/login` with the seeded admin credentials.

### Tests

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests -q        # unit (no DB needed)
TEST_MONGODB_URI=<uri> pytest tests -q                  # + Atlas integration tests
ruff check app tests && mypy app
```

## Production deployment

Deployed topology (all free-tier):

| Piece      | Where   | URL                                                  |
|------------|---------|------------------------------------------------------|
| API+worker | Render  | `https://ai-dentist-voice-agent-api.onrender.com`    |
| Dashboard  | Vercel  | `https://ai-dentist-clinic-voice-agent.vercel.app`   |
| Database   | Atlas   | `cluster0.ttdlhvh.mongodb.net` (project ai-voice-agent) |
| Telephony  | Vapi    | `+1 661 463 3323`                                    |

Render runs `backend/start.sh`, which launches the job worker alongside uvicorn in one
container (free tier has no background-worker plan; jobs are durable in MongoDB, and at
scale the worker can be split into its own service). Required env vars are in
`backend/.env.example`; production additionally needs `APP_ENV=production` and
`AUTH_COOKIE_SAMESITE=none` (cross-site cookie between Vercel and Render).

Vapi wiring: assistant `server.url` points at the webhook endpoint with a saved
`custom-credential` (HMAC-SHA256, `x-signature`/`x-timestamp` headers, `{timestamp}.{body}`
payload). Resync the assistant config by rerunning the voice-sync worker handler or
rebuilding via `app.integrations.vapi.assistant.build_assistant_config`.

## Safety & limitations

- Demo data only — synthetic patients and a fictional clinic until privacy/vendor review.
- The assistant never diagnoses, triages, prescribes, or assesses urgency; clear emergency
  statements get a redirect to emergency services.
- It never invents availability, pricing, insurance details, or booking success.
- No PHI is solicited; transcripts are stored with a retention window (default 30 days)
  purged by the worker.
- External PMS/EHR calendar sync is explicitly out of scope for the MVP.
