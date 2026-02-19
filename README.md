# Hair & Looks — Salonhub → Klaviyo Integration

FastAPI middleware that receives appointment webhooks from Salonhub, buffers them in SQLite, and syncs to Klaviyo V3 API on a nightly schedule.

## Quick Start

```bash
# Install dependencies
uv sync

# Configure
cp .env.example .env
# Edit .env with your Klaviyo API key, list ID, and webhook secret

# Run
uv run uvicorn src.main:app --reload
```

## How It Works

```
Salonhub Widget → POST /webhook/salonhub → SQLite Buffer
                                                ↓
                                          Daily at midnight
                                                ↓
                                          Aggregate per email
                                                ↓
                                          Klaviyo V3 API
```

1. Salonhub sends a webhook when a customer books or shows intent
2. The middleware validates the HMAC signature and buffers the data
3. Every night at midnight, the previous day's records are aggregated per email
4. Aggregated contacts are upserted to Klaviyo (profile + list, optionally with events)

## Modes

| Mode | What it does | Klaviyo scopes |
|------|-------------|----------------|
| `simple` | Profile upsert + add to list | `profiles:write`, `lists:write` |
| `extended` | Profile with custom properties + events (`appointmentMade`, `appointmentIntention`) | `profiles:read/write`, `lists:read/write`, `events:write` |

Set via `MODE=simple` or `MODE=extended` in `.env`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check + Klaviyo connection status |
| `GET` | `/docs` | Swagger UI |
| `POST` | `/webhook/salonhub` | Receive Salonhub webhook |
| `POST` | `/admin/trigger-daily-sync` | Manually trigger nightly sync |

## Docker

```bash
docker build -t hair-and-looks .
docker run -p 8000:8000 --env-file .env hair-and-looks
```

## Important: Salonhub Webhook Format

The Salonhub webhook payload format is **not yet documented**. The current models are a flexible best-guess. Once Salonhub shares their webhook docs, update `src/models.py` and `src/routes/webhook.py` — all locations are marked with `TODO` comments.

## Docs

- [Developer Briefing](voorstel/developer-briefing.md) — full technical reference
- [Client Proposal (NL)](voorstel/voorstel-hair-and-looks.md) — client-facing proposal in Dutch
