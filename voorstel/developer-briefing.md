# Developer Briefing: Salonhub → Klaviyo Integration

## Overview

Python FastAPI middleware that receives Salonhub appointment webhooks, buffers them in SQLite, and syncs to Klaviyo V3 API on a daily schedule. Two configurable modes: **simple** (profile + list) and **extended** (profile + custom properties + events).

## Architecture

```
Salonhub Widget → Webhook POST → FastAPI Middleware → SQLite Buffer
                                                          ↓
                                                    Daily cron (midnight)
                                                          ↓
                                                    Processor (aggregate per email)
                                                          ↓
                                                    Klaviyo V3 API
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.13 |
| Framework | FastAPI |
| Package manager | UV |
| Database | SQLite (async via aiosqlite) |
| HTTP client | httpx (async) |
| Scheduler | APScheduler v4 |
| Validation | Pydantic v2 |
| Deployment | Docker |

## Project Structure

```
src/
├── main.py              # FastAPI app, lifespan, scheduler setup
├── config.py            # Settings via pydantic-settings (.env)
├── models.py            # Pydantic models (Salonhub, Klaviyo, internal)
├── database.py          # SQLite CRUD operations (async)
├── klaviyo_client.py    # Klaviyo V3 API client with retry logic
├── processor.py         # Daily aggregation logic per email
├── scheduler.py         # Daily sync job
└── routes/
    ├── webhook.py       # POST /webhook/salonhub
    └── health.py        # GET /health, POST /admin/trigger-daily-sync
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check (Klaviyo connection + buffer stats) |
| `GET` | `/docs` | Swagger UI |
| `POST` | `/webhook/salonhub` | Receive Salonhub webhook |
| `POST` | `/admin/trigger-daily-sync` | Manually trigger daily sync |

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `MODE` | `simple` or `extended` | `simple` |
| `KLAVIYO_API_KEY` | Klaviyo private API key (`pk_...`) | — |
| `KLAVIYO_LIST_ID` | Klaviyo list ID to add profiles to | — |
| `WEBHOOK_SECRET` | HMAC-SHA256 secret for webhook verification | — |
| `DATABASE_URL` | SQLite connection string | `sqlite:///./data/intentions.db` |
| `LOG_LEVEL` | Python log level | `INFO` |

## Modes

### Simple Mode
- Upserts a Klaviyo profile (email + name)
- Adds profile to a configured Klaviyo list
- **Klaviyo scopes needed:** `profiles:write`, `lists:write`

### Extended Mode
Everything in simple mode, plus:
- Custom profile properties: `salon_naam`, `salon_id`, `kapper_naam`, `stylist_id`, `is_nieuwe_klant`, `laatste_behandeling`, `campagne_bron`
- Custom events: `appointmentMade`, `appointmentIntention`
- **Klaviyo scopes needed:** `profiles:read/write`, `lists:read/write`, `events:write`

## Webhook Flow

1. Salonhub sends `POST /webhook/salonhub` with appointment/intention data
2. Middleware verifies HMAC signature (`X-Webhook-Signature` header)
3. Payload is validated and stored in SQLite buffer
4. If no email is found in payload, the webhook is ignored (returns `{"status": "ignored"}`)
5. Returns `{"status": "buffered", "id": <int>, "type": "appointment"|"intention"}`

## Daily Aggregation Logic

Runs at midnight via APScheduler. Processes all unprocessed records from the previous day:

1. Group all buffered records by email
2. Per email, count intentions vs. appointments
3. If at least 1 appointment exists → event = `appointmentMade`
4. If only intentions (no appointment) → event = `appointmentIntention`
5. Use the most recent record for profile details
6. Send to Klaviyo (upsert profile → add to list → create event)
7. Mark all processed records in SQLite

## Klaviyo API Details

- **Base URL:** `https://a.klaviyo.com/api`
- **API Revision:** `2024-10-15`
- **Auth:** `Authorization: Klaviyo-API-Key pk_xxx`
- **Rate limiting:** Exponential backoff with up to 3 retries, respects `Retry-After` header

### Endpoints Used

| Klaviyo Endpoint | Purpose |
|------------------|---------|
| `POST /profile-import` | Upsert profile |
| `POST /lists/{id}/relationships/profiles` | Add profile to list |
| `POST /events` | Create event (extended mode only) |
| `GET /lists` | Health check / connection test |

## Salonhub Webhook Format

**The Salonhub webhook format is not yet documented.** The current payload model (`models.py`) is a flexible best-guess based on typical salon software APIs. Key areas to update once Salonhub shares their docs:

- `SalonhubWebhookPayload` — main payload structure
- `SalonhubCustomer` — customer field names and aliases
- `SalonhubAppointment` — appointment field names and aliases
- `SalonhubEventType` — event type strings
- `webhook.py` → signature header name (`X-Webhook-Signature`)
- `webhook.py` → event type detection logic

All locations are marked with `TODO` comments in the code.

## Phase 2 Preparation (Already Built In)

The following fields and properties are already wired through the entire stack (models → database → processor → Klaviyo client) but won't have data until Salonhub provides it:

- `stylist_id` / `stylist_name` — per-stylist personalization in Klaviyo flows
- `salon_id` — multi-location segmentation
- `is_new_client` — new vs. returning customer flag
- `campaign_source` — UTM/campaign attribution

## Local Development

```bash
# Install dependencies
uv sync

# Create .env from template
cp .env.example .env
# Edit .env with your Klaviyo API key, list ID, etc.

# Run the app
uv run uvicorn src.main:app --reload

# Test webhook
curl -X POST http://localhost:8000/webhook/salonhub \
  -H "Content-Type: application/json" \
  -d '{
    "eventType": "appointment.created",
    "customer": {"email": "test@example.com", "firstName": "Jan"},
    "appointment": {"salonName": "Hair & Looks", "stylistName": "Laura", "treatment": "Knippen", "price": 45.00}
  }'

# Check health
curl http://localhost:8000/health

# Trigger manual sync
curl -X POST http://localhost:8000/admin/trigger-daily-sync
```

## Docker

```bash
docker build -t hair-and-looks-integration .
docker run -p 8000:8000 --env-file .env hair-and-looks-integration
```

## Dependencies

See `pyproject.toml`. Key packages:

- `fastapi[standard]` — web framework + uvicorn
- `pydantic>=2.0` + `pydantic-settings` — validation + config
- `httpx` — async HTTP client for Klaviyo API
- `aiosqlite` — async SQLite
- `apscheduler>=4.0.0a5` — async scheduler (v4 API)
