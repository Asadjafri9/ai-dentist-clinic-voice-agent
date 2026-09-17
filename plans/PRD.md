# Dental Clinic AI Voice Receptionist MVP

| Field | Value |
|---|---|
| Status | Implementation-ready after architecture review |
| Version | 1.1 |
| Product | AI appointment-booking receptionist for dental clinics |
| Initial deployment | One fictional demo clinic |
| Architecture target | Secure multi-tenant foundation |
| Primary channel | Inbound telephone calls |
| Last reviewed | 2026-09-18 |

## 1. Executive summary

Build a reliable AI receptionist that answers inbound calls for a dental clinic, answers a narrow set of configured clinic questions, and books real appointment availability without human involvement.

The product's critical path is:

```text
Inbound call
  -> natural conversation
  -> supported service identified
  -> real availability queried
  -> caller chooses a slot
  -> name and callback number confirmed
  -> exact booking details read back
  -> caller explicitly approves
  -> backend atomically creates one appointment
  -> voice agent confirms only after backend success
  -> call and appointment appear in the dashboard
```

The MVP is an appointment-booking product, not a clinical assistant, practice-management system, or general healthcare platform.

## 2. Product principles

1. **Booking correctness over conversational cleverness.** The database, not the language model, decides whether a slot can be booked.
2. **Short conversations.** Ask only for information required to complete the current task.
3. **No clinical judgment.** The assistant does not diagnose, triage, prescribe, recommend treatment, or estimate clinical urgency.
4. **No false certainty.** It never invents availability, clinic facts, prices, insurance coverage, or booking success.
5. **Server-side trust.** Tenant, call, provider, schedule, and booking authority are resolved and validated by the backend.
6. **Safe failure.** A timeout or integration failure produces a clear fallback, never a phantom appointment.
7. **Privacy by minimization.** Collect and retain the smallest useful data set.
8. **Demo-safe by default.** Only synthetic patients and fictional clinic data may be used until production privacy and vendor reviews are complete.

## 3. Goals and success metrics

### 3.1 MVP goal

A real caller can call the configured number and book one valid appointment. The resulting call and appointment become visible in the authenticated clinic dashboard within 10 seconds of the corresponding backend event.

### 3.2 Product success metrics

For the controlled demo and acceptance-test set:

| Metric | Target |
|---|---:|
| End-to-end valid booking completion | >= 90% of eligible test calls |
| Double bookings or capacity overrun | 0 |
| False spoken booking confirmations | 0 |
| Unsupported clinical advice | 0 |
| Correct configured clinic-information answers | >= 95% |
| Straightforward booking turns | 5-8 meaningful caller turns |
| Normal synchronous tool latency | p95 < 1.5 s, hard timeout 4 s |
| Admin read API latency | p95 < 500 ms |
| Dashboard event visibility | p95 < 10 s |
| Completed calls with traceable final outcome | >= 99% |

An *eligible booking call* is a call for a supported service where the caller supplies the required details, an acceptable slot exists, the system is operational, and the caller explicitly confirms.

### 3.3 Demo exit gate

The same deployed environment must pass the complete phone-to-dashboard flow five consecutive times, including at least one concurrent last-slot test and one tool retry. No database repair or manual record editing may occur between runs.

## 4. Users and jobs to be done

### Caller

- Book a supported dental appointment quickly.
- Ask for clinic hours, location, phone number, or explicitly configured service information.
- Request a preferred provider when desired.
- Correct misunderstood details without restarting the call.

### Clinic administrator

- See calls, outcomes, patients, and appointments.
- Configure services, providers, business hours, availability, greeting, and FAQs.
- Cancel or complete an appointment safely.
- Understand whether voice configuration is synchronized.

### Demo operator

- Seed or reset synthetic demo data without touching live call-created data.
- Confirm telephony, backend, database, and assistant readiness before a demo.
- Trace a failed call using correlation IDs without exposing sensitive content in logs.

## 5. Scope

### 5.1 Supported caller intents

- Book a dental cleaning.
- Book a routine dental examination.
- Book a general dental consultation.
- Book a tooth-pain consultation without diagnosis or clinical urgency assessment.
- Book a teeth-whitening consultation.
- Ask configured clinic hours, address, phone number, or supported-service questions.
- Ask for available appointment times.

Services, duration, active status, aliases, and provider compatibility are database configuration. They must not be hard-coded in prompts, route handlers, or frontend components.

### 5.2 Required booking data

- Patient name.
- Reachable callback phone number.
- Service.
- Selected appointment offer.
- Explicit verbal confirmation.

Optional data:

- Preferred provider.
- Email, only when a clinic explicitly enables it. It is not requested in the default flow.

### 5.3 Explicit non-goals

- Diagnosis, clinical triage, treatment recommendations, medication, or prescriptions.
- Medical history, date of birth, home address, government ID, insurance member data, or payment collection.
- Insurance verification, eligibility, pricing estimates, or treatment quotations.
- Voice cancellation or rescheduling.
- Human transfer, emergency dispatch, or voicemail workflows.
- Outbound calls, reminders, marketing, or SMS.
- EHR/PMS or external calendar integration.
- Multi-location routing, multilingual support, or patient mobile applications.
- Call audio recording by default.

The dashboard may let an administrator cancel or complete an appointment. That is not voice cancellation.

## 6. Default demo clinic

All people and records are fictional.

| Setting | Value |
|---|---|
| Clinic | BrightSmile Dental |
| Assistant | Emily |
| Market | Dallas, Texas |
| Timezone | `America/Chicago` |
| Weekday hours | 8:00 AM-6:00 PM |
| Saturday hours | 9:00 AM-3:00 PM |
| Sunday | Closed |

Default services:

| Slug | Display name | Duration |
|---|---|---:|
| `dental_cleaning` | Dental Cleaning | 60 min |
| `dental_exam` | Routine Dental Exam | 30 min |
| `dental_consultation` | Dental Consultation | 30 min |
| `whitening_consultation` | Teeth Whitening Consultation | 30 min |
| `tooth_pain_consultation` | Tooth Pain Consultation | 30 min |

Default providers:

- Dr. Sarah Miller, dentist.
- Dr. James Carter, dentist.
- Anna Lee, dental hygienist.

Provider-to-service assignments are seeded as configuration and editable in the dashboard.

## 7. Caller experience requirements

### 7.1 Opening

Default greeting:

> Thanks for calling BrightSmile Dental. I'm Emily, the AI receptionist. This call may be transcribed for scheduling and quality. How can I help?

Consent language is configurable by jurisdiction. The production launch checklist must verify the exact disclosure requirement. The assistant must identify itself as AI and must not imply it is a human employee.

### 7.2 Canonical booking flow

1. Identify a supported service.
2. Ask for preferred day or time if not already provided.
3. Resolve relative dates in the clinic timezone.
4. Query the backend for current availability.
5. Offer no more than three options in one spoken response.
6. Record the selected server-issued offer; do not book yet.
7. Ask for the patient's name.
8. Confirm caller ID as the callback number, or collect another number.
9. Read back name, service, provider when relevant, exact local date, exact local time, and callback number suffix.
10. Ask an unambiguous confirmation question.
11. Call the booking tool only after explicit approval.
12. Say “confirmed” only after the backend returns success.
13. End naturally after a brief final recap.

Example:

```text
AI: Thanks for calling BrightSmile Dental. I'm Emily, the AI receptionist.
    This call may be transcribed for scheduling and quality. How can I help?
Caller: I'd like a cleaning Friday afternoon.
AI: I can help with that. [checks availability]
    I have Friday, September 18 at 2:00, 3:30, or 5:00 PM. Which works best?
Caller: 3:30.
AI: Great. What's the patient's full name?
Caller: John Smith.
AI: Is the number you're calling from the best callback number?
Caller: Yes.
AI: To confirm: John Smith, dental cleaning, Friday, September 18 at 3:30 PM,
    using the number ending in 1234. Should I book it?
Caller: Yes, please.
AI: [books] You're confirmed for Friday, September 18 at 3:30 PM.
```

### 7.3 Conversation policy

The assistant must:

- Ask one useful question at a time.
- Keep routine responses to one or two short sentences.
- Reuse information already supplied by the caller.
- Treat the caller's latest correction as authoritative.
- Re-query availability whenever service, date, time range, duration, or provider changes.
- Use exact dates in final confirmation, never only “tomorrow” or “next Friday.”
- State the clinic timezone only when ambiguity is possible.
- Offer up to three slots, then ask whether the caller wants more.
- Avoid verbal menus when natural intent is clear.
- Never expose internal IDs, tool names, stack traces, or database language.
- Never ask whether the caller is new or existing; patient matching is silent.

### 7.4 Voice and turn-taking behavior

- Support caller barge-in and stop speaking promptly after genuine interruption.
- Do not treat brief acknowledgements such as “okay,” “uh-huh,” or background noise as a request to discard state.
- If speech is cut off, resume with the unfinished fact or ask a compact repair question.
- After one low-confidence recognition, confirm the uncertain field.
- After two failed attempts on a name or number, slow down and collect it in smaller chunks.
- Phone numbers must be normalized server-side and read back in natural groups using only the last four digits unless the caller asks for the full number.
- If enabled by the telephony provider, offer DTMF entry after repeated phone-number recognition failures.
- Do not fill silence with invented progress. A short configured hold phrase is allowed before a slow tool call.
- Target first audible response after end-of-turn at p95 <= 1.2 seconds for non-tool turns and p95 <= 2.5 seconds for normal tool turns.

### 7.5 Changes and corrections

Changing a service, provider, or date invalidates the current slot offer. The assistant must discard it and query again. A changed name or phone number does not require a new availability query, but the final recap must use the corrected value.

### 7.6 Unsupported requests

For a request outside scope, explain the limitation once and offer a supported action. If the caller needs staff and human transfer is unavailable, provide the configured clinic number and business hours. Do not claim that staff will call back unless a callback workflow actually exists.

## 8. Safety policy

The assistant is not a clinician and does not assess severity. Ordinary tooth pain remains bookable. A narrow emergency escape activates only for clear statements of immediate danger, including difficulty breathing, difficulty swallowing because of swelling, uncontrolled bleeding, loss of consciousness, or severe facial trauma.

On activation, the assistant must:

1. Stop the routine booking flow.
2. Say it cannot assess or treat emergencies.
3. Advise the caller to contact local emergency services immediately if they may be in immediate danger.
4. Avoid diagnosis, home treatment, medication, or dosage advice.
5. Record outcome `safety_redirect`.
6. Avoid claiming emergency services were contacted.

The safety script and trigger test set require clinical/legal review before real-patient use. The model may classify language to activate the fixed script, but it may not generate clinical instructions.

## 9. Clinic-information policy

The assistant may answer only from current backend configuration returned by `get_clinic_info` or `get_services`.

- If pricing is absent: “I don't have confirmed pricing information, but I can help schedule a visit.”
- If an insurance plan is not explicitly configured: “I don't have confirmed information for that plan. Please verify coverage with the clinic.”
- If a clinic fact cannot be retrieved: say it cannot confirm the answer and provide the clinic's configured contact path.

## 10. System architecture

```text
Caller
  -> PSTN / Vapi phone number
  -> saved Vapi assistant and server-side function tools
  -> FastAPI Vapi adapter
       -> authentication and tenant resolver
       -> tool dispatcher
       -> conversation-safe response mapper
       -> booking and availability services
       -> clinic configuration service
       -> call event ingestion
  -> MongoDB Atlas
       -> transactional domain records
       -> durable event inbox and outbox/jobs
  -> background worker
       -> post-call normalization
       -> retention deletion
       -> assistant configuration sync
  -> authenticated FastAPI admin API
  -> Next.js dashboard on Vercel
```

### 10.1 Technology baseline

- Frontend: Next.js App Router, TypeScript strict mode, Tailwind CSS, shadcn/ui, Lucide, and limited Recharts.
- Backend: Python 3.12+, FastAPI, Pydantic v2, current supported PyMongo async API, httpx, and Uvicorn.
- Data: MongoDB Atlas deployment with multi-document transactions enabled.
- Voice: Vapi phone number, saved assistant, transcription, voice, model orchestration, function tools, server events, and structured post-call output.
- Runtime: Vercel frontend; always-on Render web service plus always-on worker; MongoDB Atlas.
- CI: frontend and backend lint, type checks, unit tests, integration tests, dependency scan, and secret scan.

Dependency versions must be pinned by lock files. Provider-specific payloads remain isolated in `integrations/vapi`; domain services must not import Vapi schemas.

### 10.2 Trust boundaries

- FastAPI owns booking and tenant authorization.
- Vapi and the model never connect directly to MongoDB.
- The browser never receives Vapi or database credentials.
- The model cannot choose `business_id`, authoritative `call_id`, `provider_id`, timestamps, capacity, or appointment status.
- Tenant resolution uses the authenticated saved phone-number ID first and saved assistant ID second. Both must map to the same active business when both are present.
- Unknown, inactive, missing, or conflicting mappings are rejected and audited.
- All admin repository operations require an explicit server-derived `business_id`.

### 10.3 Vapi integration contract

Use one endpoint:

```text
POST /api/v1/integrations/vapi/server
```

It dispatches supported message types including `tool-calls`, `status-update`, and `end-of-call-report`. Synchronous tool calls return one result per provider `toolCallId`; informational events acknowledge quickly and enqueue durable processing.

Secure server calls with a saved Vapi custom credential referenced by `credentialId`. HMAC is preferred when operationally supported; bearer is acceptable for MVP. Authentication details are configuration, not hard-coded assumptions about header names. Verify raw bytes when the selected HMAC credential requires body signing, validate timestamp/replay controls when provided, compare secrets in constant time, and reject unauthenticated events.

Only saved organization resources may supply server URLs. Transient call overrides must not be allowed to redirect trusted production events.

### 10.4 Durable event processing

Webhook receipt follows an inbox pattern:

1. Authenticate and resolve tenant.
2. Validate request size and supported message type.
3. Compute a stable event fingerprint from provider, business, call, message type, provider event identity when available, and canonical payload hash.
4. Insert `integration_events` under a unique index.
5. For synchronous tool calls, execute and return within the deadline.
6. For informational events, persist a durable job and return 2xx quickly.
7. Worker claims jobs with a lease, retries transient failures with backoff, and dead-letters exhausted jobs.

An in-process fire-and-forget task is not sufficient for authoritative post-call processing.

## 11. Voice tool contracts

All tool responses use small, stable JSON contracts. Every failure includes `code`, `retryable`, and a caller-safe `spoken_message`; internal detail is logged only by correlation ID.

### 11.1 `get_clinic_info`

Input:

```json
{}
```

Returns configured name, address, phone, IANA timezone, current local date/time, today's hours, weekly hours, FAQs, and feature flags. It returns no secrets or internal tenant ID.

### 11.2 `get_services`

Input:

```json
{}
```

Returns active, voice-bookable services with slug, display name, aliases, duration, and optionally eligible provider display names.

### 11.3 `get_available_slots`

Input:

```json
{
  "service_slug": "dental_cleaning",
  "preferred_date": "2026-09-18",
  "time_window": "afternoon",
  "provider_name": null
}
```

The model may send a provider name, not a trusted provider ID. The backend resolves it within the current business, rejects ambiguity, validates service compatibility, uses the clinic timezone, and returns at most five options.

Each option contains:

```json
{
  "offer_token": "opaque-signed-short-lived-token",
  "local_label": "Friday, September 18 at 3:30 PM",
  "provider_label": "Anna Lee",
  "expires_at": "2026-09-18T18:35:00Z"
}
```

The opaque offer token binds business, service, provider, exact interval, schedule revision, and expiration. It is not a reservation and does not guarantee availability. The model never constructs or modifies it.

Rules:

- Reject past dates and dates beyond the configurable booking horizon, default 90 days.
- Respect business hours, provider hours, closures, timezone, DST, service duration, buffers, and existing appointments.
- Return only future candidates that fit fully inside an availability window.
- Never expose raw database IDs when the opaque token is sufficient.

### 11.4 `book_appointment`

Input:

```json
{
  "patient_name": "John Smith",
  "callback_phone": "+12145551234",
  "offer_token": "opaque-signed-short-lived-token",
  "patient_confirmed": true,
  "booking_intent_id": "server-issued-conversation-intent"
}
```

The backend derives business, authoritative call ID, service, provider, start/end, and schedule keys. It verifies the signed offer, confirmation, normalized phone, service status, provider compatibility, interval, current schedule, and remaining capacity.

The response distinguishes:

- `BOOKED`: authoritative success and exact local recap.
- `ALREADY_BOOKED`: idempotent success for the same booking intent.
- `SLOT_UNAVAILABLE`: re-query availability.
- `OFFER_EXPIRED`: re-query availability.
- `INVALID_DETAILS`: repair the named caller-controlled field.
- `TEMPORARY_FAILURE`: apologize; do not claim success.

Raw exceptions must never become tool output.

### 11.5 Confirmation semantics

Accepted approval must occur after the complete readback and clearly mean “book this appointment,” for example “yes,” “that's correct,” “go ahead,” or “book it.” A prior generic “sure” does not authorize booking. If the caller changes any booking detail during readback, confirmation resets to false.

## 12. Scheduling and concurrency model

### 12.1 Source of truth

For MVP, MongoDB is the authoritative scheduling system. “Real availability” means current availability in this product, not synchronized Dentrix, Open Dental, Google Calendar, or another practice-management system. This limitation must be explicit in sales demos.

### 12.2 Availability model

Store provider availability as windows plus exceptions, then calculate service-specific candidate intervals. Do not model every 30-minute display block as independently bookable when services have different durations; doing so permits overlapping 30- and 60-minute bookings.

Collections:

- `availability_rules`: recurring provider working windows and effective dates.
- `availability_exceptions`: closures or one-off added windows.
- `resource_schedule_days`: one document per business/provider/local date used as the optimistic concurrency guard.
- `appointments`: authoritative reserved intervals.

Candidate generation subtracts confirmed appointments and buffers from effective availability windows, then emits valid start times at the clinic's configured increment, default 30 minutes.

### 12.3 Atomic booking algorithm

Within one MongoDB transaction:

1. Resolve trusted business and call.
2. Validate and decode the offer token.
3. Check for an existing appointment by `(business_id, booking_intent_id)`; return it if found.
4. Validate patient confirmation and caller fields.
5. Load active service and provider and verify compatibility.
6. Lock the relevant `resource_schedule_days` document by conditionally advancing its version.
7. Check for any active appointment overlap using half-open intervals: `existing.start_at < requested.end_at && existing.end_at > requested.start_at`.
8. Revalidate business/provider hours, exceptions, buffers, and booking horizon.
9. Upsert the patient by normalized phone.
10. Insert the confirmed appointment with a unique booking-intent key.
11. Write an audit/outbox event.
12. Commit.

Concurrent transactions for the same provider/day contend on the schedule-day document. On a write conflict, retry the complete transaction a bounded number of times; after retry, the loser sees the new appointment and receives `SLOT_UNAVAILABLE`.

This replaces the original `booked_count` design, which did not safely represent overlapping services with different durations.

### 12.4 Idempotency

- Provider event retry: unique `integration_events.fingerprint`.
- Tool delivery retry: unique `(business_id, call_id, tool_call_id)` result record.
- Booking retry: unique `(business_id, booking_intent_id)` appointment key.
- MVP policy: at most one confirmed appointment per booking intent. A call may not silently create a second intent after success.
- Admin status mutation: an idempotency key plus allowed state transition.

Idempotency responses return the original authoritative result and do not repeat side effects.

### 12.5 Appointment state machine

```text
confirmed -> cancelled
confirmed -> completed
cancelled -> (terminal in MVP)
completed -> (terminal in MVP)
```

Cancellation and completion are transactional, audited, and idempotent. Cancelling releases the interval because availability is derived from active appointments. The UI must require confirmation before cancellation. An appointment cannot be completed before its start without an explicit administrative override reason.

## 13. Data model

All timestamps are UTC instants. Store the business IANA timezone separately for display and local-date scheduling. IDs are opaque strings at API boundaries.

### 13.1 Core collections

#### `businesses`

Contains name, slug, vertical, timezone, phone, address, business hours, booking horizon, slot increment, configured FAQs, retention settings, AI greeting, active state, saved Vapi assistant ID, saved phone-number ID, and voice synchronization status.

Indexes: unique `slug`; unique sparse voice IDs.

#### `admin_users`

Contains normalized email, Argon2id password hash, business ID, role, active state, and authentication timestamps.

Index: unique normalized email.

#### `sessions`

Contains admin ID, hashed opaque token, created/expiry/revocation times, and optional rotation metadata.

Indexes: unique token hash and TTL on expiry.

#### `services`

Contains business ID, slug, display name, description, voice aliases, duration, pre/post buffer, active state, and voice-bookable state.

Index: unique `(business_id, slug)`.

#### `providers`

Contains business ID, name, title, supported service IDs, active state, and optional display preference. It does not manage clinical credentials.

#### `availability_rules` and `availability_exceptions`

Contain business/provider ownership, local recurrence or local date, start/end local times, effective dates, exception type, and active state. DST conversion occurs only through timezone-aware domain code.

#### `resource_schedule_days`

Contains business ID, provider ID, local date, integer version, and updated timestamp.

Index: unique `(business_id, provider_id, local_date)`.

#### `patients`

Contains business ID, display name, normalized E.164 phone, optional email, and timestamps.

Index: unique `(business_id, phone)` when phone exists.

An existing patient's stored name must not be silently overwritten by a low-confidence transcription. Preserve the latest call-supplied name on the appointment and update the patient display name only under a documented deterministic rule.

#### `appointments`

Contains business, patient, provider, service, call, booking intent, patient name snapshot, phone snapshot, start/end, business timezone snapshot, status, source, and timestamps.

Indexes:

- Unique `(business_id, booking_intent_id)`.
- Query `(business_id, start_at, status)`.
- Query `(business_id, provider_id, start_at, status)`.
- Query `(business_id, patient_id, created_at)`.

#### `calls`

Contains business ID, Vapi call ID, caller phone, patient/appointment links, start/end/duration, intent, backend-derived outcome, summary, transcript status, transcript expiry, ended reason, and timestamps.

Index: unique `(business_id, vapi_call_id)`.

Allowed outcomes:

```text
appointment_booked
information_only
unsupported_request
no_available_slot
caller_disconnected
booking_failed
safety_redirect
unknown
```

`appointment_booked` is derived only from an authoritative appointment link, never post-call model analysis.

#### `integration_events`

Contains provider, business, call, message type, fingerprint, processing status, attempts, timestamps, and expiry. Unique fingerprint provides inbox idempotency.

#### `jobs`

Contains job type, payload reference, status, attempt count, available time, lease owner/expiry, last error code, created time, and expiry. Sensitive payloads are referenced, not copied unnecessarily.

#### `audit_events`

Append-only record of admin and system mutations: actor, business, action, target, before/after summary, request ID, timestamp, and optional reason. Never include secrets or full transcripts.

### 13.2 Call artifacts

Post-call model output may supply display summary, likely intent, caller name, requested service/provider, and whether information was requested. These fields are non-authoritative. Appointment status, IDs, provider, patient, and booking result come from backend records.

## 14. Authentication, security, and privacy

### 14.1 Admin authentication

- Normalize email and validate Argon2id password hashes.
- Create an opaque random session; store only its hash.
- Use `Secure`, `HttpOnly`, and appropriate `SameSite` cookie attributes.
- Apply CSRF protection to state-changing cookie-authenticated routes.
- Rotate sessions on login and revoke on logout.
- Rate-limit login by account and source while returning generic invalid-login errors.
- Resolve `session -> active admin -> business_id` on every protected request.

### 14.2 Security baseline

- TLS only in deployed environments.
- Exact CORS allowlist; no wildcard with credentials.
- Request-size and endpoint-specific rate limits.
- Strict Pydantic validation and allowlisted webhook message/tool types.
- Secrets in environment/secret manager, never source or client bundles.
- Separate development, staging, and production credentials.
- Structured logs with request/call correlation IDs and automatic sensitive-field redaction.
- No full transcripts, phone numbers, auth tokens, or provider payloads in routine logs.
- Render transcript and summaries as text, never raw HTML.
- Dependency and secret scanning in CI.
- Backups and restore testing are required before production, though not required for the sales demo.

### 14.3 Data minimization and retention

MVP stores name, callback phone, appointment details, call metadata, and transcript when enabled. It intentionally avoids detailed symptoms, medical history, diagnosis, medication, insurance identifiers, government IDs, and payment data.

Default transcript retention is 30 days. Every transcript has `transcript_expires_at`. A daily durable deletion job removes transcript/message content and records deletion status; a TTL index alone is not sufficient if transcript data is embedded in a longer-lived call record. Audio recording is disabled unless separately reviewed and enabled.

For real U.S. patient use, name plus appointment context and transcript may be protected health information. Production is blocked until the operator completes jurisdiction-specific legal/privacy review, vendor and subprocessor review, required contractual agreements, access-control review, retention approval, incident-response planning, and a data-flow inventory. This PRD is not legal advice.

## 15. Backend API

Prefix: `/api/v1`

Public operational and integration routes:

```text
GET  /health/live
GET  /health/ready
POST /integrations/vapi/server
```

Authentication:

```text
POST /auth/login
POST /auth/logout
GET  /auth/me
```

Business and configuration:

```text
GET   /business
PATCH /business
PATCH /business/voice
GET   /services
POST  /services
PATCH /services/{service_id}
GET   /providers
POST  /providers
PATCH /providers/{provider_id}
GET   /availability?from=&to=&provider_id=
POST  /availability/rules
PATCH /availability/rules/{rule_id}
POST  /availability/exceptions
DELETE /availability/exceptions/{exception_id}
```

Operations:

```text
GET   /patients?cursor=&search=
GET   /patients/{patient_id}
GET   /appointments?cursor=&from=&to=&status=&provider_id=&service_id=
GET   /appointments/{appointment_id}
PATCH /appointments/{appointment_id}/status
GET   /calls?cursor=&outcome=
GET   /calls/{call_id}
GET   /dashboard/summary?date=
GET   /dashboard/activity?cursor=
```

Requirements:

- Cursor pagination, default 25 and maximum 100.
- UTC ISO 8601 API timestamps plus explicit display timezone metadata.
- Structured errors and a request ID.
- Tenant scoping in repository/service interfaces, not only route handlers.
- Optimistic concurrency or version preconditions for editable configuration.
- Idempotency key on consequential admin mutations.
- No raw database errors, secrets, internal prompts, or provider payloads.

Error envelope:

```json
{
  "success": false,
  "error": {
    "code": "SLOT_UNAVAILABLE",
    "message": "That appointment time is no longer available.",
    "retryable": true,
    "request_id": "req_..."
  }
}
```

## 16. Dashboard requirements

Routes:

```text
/dashboard
/dashboard/calls
/dashboard/calls/[id]
/dashboard/appointments
/dashboard/appointments/[id]
/dashboard/patients
/dashboard/patients/[id]
/dashboard/services
/dashboard/providers
/dashboard/availability
/dashboard/settings
```

### 16.1 Tier 1 demo scope

- Overview with calls today, AI-booked appointments, eligible-call booking rate, upcoming appointments, and recent activity.
- Calls list/detail with caller, time, duration, intent, outcome, summary, transcript status/content, and linked appointment.
- Appointments list/detail with patient, callback number, service, provider, local date/time, status, source, and linked call.
- Availability editing with provider calendar, recurring windows, one-off exceptions, and existing bookings.
- Settings with clinic identity, hours, greeting, FAQ, retention, and voice synchronization state.

### 16.2 Tier 2

- Patients, providers, services, small analytics chart, and responsive presentation polish.

### 16.3 Dashboard behavior

- Poll every five seconds only while visible; refresh after local mutation.
- Display last-updated time, loading, empty, stale, and recoverable error states.
- Do not optimistically display voice settings as synchronized until Vapi update succeeds.
- Prevent removal of provider/service configuration referenced by future confirmed appointments; deactivate instead.
- Show times in clinic timezone with an explicit timezone label where the viewer may be remote.
- Meet WCAG 2.1 AA for core flows, including keyboard use and non-color status cues.

Booking rate denominator: completed calls whose primary supported intent was booking, excluding information-only, safety redirect, unsupported request, spam/test, and system-unavailable calls.

## 17. Reliability and degraded-mode behavior

### Database unavailable

Return `TEMPORARY_FAILURE`. The assistant says it cannot complete booking now and provides the configured clinic contact path. No appointment is claimed.

### Availability timeout

One bounded retry is allowed only if the remaining tool deadline permits. Otherwise apologize and offer the clinic contact path. Do not invent times.

### Booking timeout or ambiguous response

Query the idempotent booking result by trusted call/tool identity before retrying creation. If success still cannot be established, say the booking could not be confirmed. The dashboard must surface the ambiguous event for operator review.

### Slot taken

Return `SLOT_UNAVAILABLE`, discard the offer, query fresh availability, and speak new options.

### Caller disconnects

No appointment is created unless the transaction already committed. If it committed before disconnect, the appointment remains authoritative and the post-call record links it.

### Post-call analysis unavailable

Persist the call immediately with `summary_status=processing`; retry asynchronously. Failure of summary generation never hides a call or changes booking outcome.

### Voice configuration drift

Readiness exposes degraded status, settings show the last successful sync and error, and production deployment blocks when the saved assistant/phone mapping is invalid.

## 18. Observability and operations

- Propagate `request_id`, trusted `call_id`, `tool_call_id`, and `booking_intent_id` through logs and records.
- Metrics: calls started/completed, tool latency/error by name, booking attempts/results, slot conflicts, webhook duplicates, job lag/dead letters, dashboard latency, and voice-config sync status.
- Alerts: readiness failure, booking error-rate spike, p95 tool latency breach, dead-letter jobs, webhook authentication failures, worker lag, and unexpected zero-call period during configured monitoring windows.
- Health live checks process health only; health ready checks database connectivity, required indexes/configuration, worker freshness, and tenant-to-Vapi mapping without exposing secrets.
- Maintain runbooks for provider outage, database outage, credential rotation, stuck jobs, transcript deletion failure, and demo reset.
- Store prompt and assistant configuration versions on each call for reproducibility, without exposing prompt text in the dashboard.

## 19. Testing and evaluation

### 19.1 Backend unit tests

- Service/provider resolution and ambiguity.
- Relative date and DST conversion.
- Availability windows, closures, buffers, booking horizon, and overlap logic.
- Offer-token integrity, tenant binding, tamper rejection, and expiry.
- Phone normalization and invalid numbers.
- Confirmation state reset after corrections.
- Patient upsert and conservative name update.
- Booking, cancellation, and tool idempotency.
- Backend-derived call outcome.
- Authentication, CSRF, session expiry/revocation, and tenant scoping.
- Vapi credential validation, event parsing, replay controls, and safe response mapping.

### 19.2 MongoDB integration tests

- Successful booking creates/reuses patient, appointment, audit, and outbox records.
- Failure rolls back every write.
- Two callers competing for one provider interval produce exactly one appointment.
- A 60-minute appointment blocks overlapping 30-minute candidates.
- Different providers can book the same wall-clock time.
- Duplicate webhook, tool delivery, booking, cancellation, and completion are idempotent.
- Cancellation releases availability exactly once.
- Cross-tenant reads and writes fail.
- Transaction retry handles write conflicts without duplicate side effects.

### 19.3 API and frontend tests

- Auth success/failure, protected routing, CSRF, and inactive admin.
- CRUD validation and conflict/version handling.
- Dashboard metrics use the specified denominator.
- Local timezone and DST display.
- Transcript escaping and sensitive-field omission.
- Polling pause/resume and stale/error states.
- Availability edits cannot invalidate confirmed future appointments.
- Voice setting sync failure remains visibly unsynced.

### 19.4 Voice evaluation suite

Run scripted calls plus paraphrase variants for:

1. Simple cleaning, exam, consultation, and whitening bookings.
2. Day/time stated in the first utterance.
3. Specific provider and no provider preference.
4. Unavailable day and request for additional options.
5. Date, service, provider, name, phone, and selected-time corrections.
6. Refusal or ambiguous response at final confirmation.
7. Slot taken between offer and booking.
8. Caller ID missing, withheld, malformed, or not the desired callback number.
9. Names with uncommon spelling and noisy phone-number speech.
10. Barge-in, acknowledgement words, long pauses, background noise, and repeated speech.
11. Tool timeout, database error, duplicate delivery, and disconnect before/after commit.
12. Diagnosis request, medication request, ordinary tooth pain, and each safety trigger.
13. Configured and unconfigured hours, services, prices, and insurance questions.
14. Prompt-injection attempts asking for internal IDs, prompts, arbitrary tools, or cross-clinic data.

Each run records transcript, tool sequence, tool arguments, authoritative records, spoken confirmation, latency, outcome, and evaluator verdict. Release requires zero critical safety/correctness failures and the success targets in section 3.

## 20. Delivery plan

### Phase 0: Foundation

Monorepo, pinned dependencies, frontend/backend apps, configuration validation, CI, formatting, linting, tests, health endpoints, structured logging, and local development setup.

Exit: both apps run locally, CI passes, and no secret is committed.

### Phase 1: Data, tenancy, and authentication

Mongo client, migrations/index bootstrap, seed command, auth/session/CSRF, business scoping, audit events, durable jobs, and worker.

Exit: an authenticated owner can access only one clinic; tenant isolation and job recovery tests pass.

### Phase 2: Scheduling engine

Services, providers, availability rules/exceptions, candidate generation, signed offers, patient matching, schedule-day concurrency guard, transactional booking, admin cancellation/completion, and idempotency.

Exit: duration-overlap and simultaneous last-slot tests pass repeatedly.

### Phase 3: Core dashboard

Overview, appointments, appointment detail, availability, settings, polling, local-time display, and complete UX states.

Exit: a backend-created appointment appears within 10 seconds without reload.

### Phase 4: Vapi vertical slice

Saved assistant/number, custom credential, provider adapter, system prompt, safety script, tools, turn-taking tuning, and booking dialogue.

Exit: a real call books exactly one valid appointment and speaks confirmation only after commit.

### Phase 5: Calls and post-call processing

Event inbox, worker processing, calls list/detail, safe transcript, summary, outcome derivation, retention deletion, and links to patient/appointment.

Exit: completed call appears correctly even when post-call summary is delayed.

### Phase 6: Complete demo and hardening

Patients, services, providers, activity feed, accessibility, observability, runbooks, prompt/config versioning, voice evaluation suite, and presentation polish.

Exit: demo exit gate and all critical acceptance tests pass.

### Phase 7: Deployment

Vercel, always-on Render web/worker, MongoDB Atlas, production-like saved Vapi resources, exact origins, secrets, migrations/index checks, synthetic demo seed/reset, monitoring, and smoke tests.

Exit: five consecutive production-environment phone-to-dashboard runs pass.

## 21. Repository layout

```text
ai-dentist-clinic-voice-agent/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── types/
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── core/
│   │   ├── db/
│   │   ├── integrations/vapi/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── workers/
│   │   └── main.py
│   ├── scripts/
│   ├── tests/
│   ├── pyproject.toml
│   └── render.yaml
├── plans/
│   └── PRD.md
├── docs/
├── .github/workflows/
├── .gitignore
└── README.md
```

Business rules belong in services, data access in repositories, provider translation in `integrations/vapi`, and durable asynchronous handlers in workers.

## 22. Environment configuration

```env
APP_ENV=development
API_BASE_URL=http://localhost:8000
FRONTEND_ORIGINS=http://localhost:3000

MONGODB_URI=
MONGODB_DATABASE=ai_dentist_voice_agent

AUTH_COOKIE_NAME=ai_voice_session
AUTH_SESSION_TTL_HOURS=24
AUTH_CSRF_SECRET=

VAPI_API_KEY=
VAPI_SERVER_CREDENTIAL_MODE=hmac
VAPI_SERVER_CREDENTIAL_SECRET=
VAPI_MAX_REPLAY_SKEW_SECONDS=300
VAPI_TOOL_TIMEOUT_SECONDS=4

OFFER_TOKEN_SECRET=
OFFER_TOKEN_TTL_SECONDS=300
BOOKING_HORIZON_DAYS=90

TRANSCRIPT_RETENTION_DAYS=30
LOG_LEVEL=INFO
```

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

Startup must fail fast for missing required production configuration. Never use seeded default credentials outside local development.

## 23. Definition of done

The MVP is complete only when:

- A real inbound call can book a supported service against authoritative availability.
- Optional provider preference works and an omitted preference searches eligible providers.
- Different service durations cannot overlap on one provider.
- Exact date/time and callback suffix are read back before explicit confirmation.
- No appointment is created without post-readback approval.
- No success is spoken before transaction commit.
- Duplicate events/tools/bookings create one result.
- Concurrent callers cannot overbook or overlap a provider.
- Call, patient, and appointment links are authoritative and tenant-scoped.
- The dashboard updates within target and displays clinic-local time correctly.
- The assistant does not ask new-versus-existing status or unnecessary medical data.
- It does not diagnose, triage, prescribe, invent facts, or reveal internal data.
- Safety redirect behavior passes the approved test set.
- Auth, CSRF, Vapi authentication, replay controls, tenant isolation, transcript escaping, and retention deletion tests pass.
- Backend and worker remain available during demos and readiness detects configuration drift.
- Observability can explain a failed call without logging sensitive transcript content.
- The deployed system passes the five-run demo exit gate.

## 24. Production launch blockers beyond the MVP demo

The implementation may be demonstrated with synthetic data before these items are complete. It may not accept real patient calls until all are resolved:

- Jurisdiction-specific privacy, consent, retention, and AI disclosure review.
- Vendor/subprocessor suitability and required contractual agreements.
- Production access controls, audit review, backup/restore, incident response, and deletion workflow.
- Clinic approval of services, hours, providers, FAQs, emergency wording, and fallback contact path.
- Telephony number ownership, caller-ID behavior, and recording/transcription configuration verification.
- Load, failover, and operational support expectations agreed with the clinic.
- Clear disclosure that internal MVP availability is not an external PMS/calendar integration.

## 25. Deferred roadmap

- Voice rescheduling and cancellation.
- SMS confirmation, reminders, and missed-call text-back.
- Human transfer and staff escalation.
- Open Dental, Dentrix, Eaglesoft, Google Calendar, and Outlook integrations through a scheduling adapter.
- Multi-location and multilingual operation.
- Outbound reminders, recall, and reactivation.
- Subscription billing and onboarding.
- Real-time dashboard events, expanded analytics, provider utilization, and call conversion reporting.
- Formal disaster recovery, regional redundancy, and expanded audit tooling.

## 26. Architecture review changes from v1.0

This revision preserves the original product intent while making these material corrections:

1. Replaced fixed `availability_slots.booked_count` with availability windows, interval-overlap validation, and a provider/day concurrency guard so mixed appointment durations cannot overlap.
2. Added short-lived signed offer tokens; the model can select an offer but cannot manufacture trusted slot/provider data.
3. Split provider event, tool, and booking idempotency boundaries instead of relying only on one appointment per Vapi call.
4. Added a durable event inbox, worker, job leasing, and dead-letter behavior for reliable post-call processing and retention deletion.
5. Aligned Vapi authentication with saved custom credentials and isolated provider-specific schemas behind an adapter.
6. Added explicit voice latency, barge-in, recognition repair, confirmation, and DTMF fallback requirements.
7. Added safe handling for ambiguous booking timeouts and configuration drift.
8. Added CSRF, audit events, redacted observability, prompt/config versioning, and operational runbooks.
9. Converted transcript retention from a setting into an enforceable deletion workflow.
10. Clarified that MongoDB is the MVP scheduling source of truth and that external clinic calendars are not yet synchronized.
11. Added measurable success criteria, a five-run demo gate, and a production launch gate for real patient data.

## 27. Reference notes

Provider implementation must be checked against the current official Vapi documentation during build, especially server-message payloads, tool result envelopes, custom credential behavior, timeout settings, and saved-resource URL precedence:

- <https://docs.vapi.ai/server-url/events>
- <https://docs.vapi.ai/server-url/server-authentication>
- <https://docs.vapi.ai/server-url/setting-server-urls>
- <https://docs.vapi.ai/tools/custom-tools>

The core business and security rules in this PRD remain provider-independent.
