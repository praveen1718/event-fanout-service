# Event Fanout Service — Engineering Conventions

FastAPI service: ingest structured events, match them against subscriber filter rules, deliver
to webhook endpoints with retries, expose a delivery audit trail. Deliverable is the GitHub
repo (code + architecture diagram); no live deploy.

## Commands
- Install: `make install` (editable install with dev extras)
- Run locally: `make run` (uvicorn on :8080, reload)
- Test: `make test` (pytest) — run after every change
- Lint: `make lint` (ruff) — must pass before committing
- Docker: `make docker-build && make docker-run` (no docker CLI in this dev container; CI builds it)

## Architecture (keep these layers separate)
- `app/api/` — thin HTTP handlers only: validate → call service → respond. No business logic.
- `app/services/` — business logic, testable without a server. New features start here.
- `app/repositories/` — the only place SQL/ORM queries live; Postgres is a `DATABASE_URL` swap.
- `app/db/` — engine/session factory and ORM table definitions.
- `app/models/schemas.py` — all request/response contracts as Pydantic models.
- `app/core/config.py` — 12-factor config: env vars only, never hardcode values or secrets.
- `app/core/logging.py` + `middleware.py` — structured JSON logging with request IDs.

## Non-negotiable standards (production-readiness is being evaluated)
- Every endpoint: Pydantic input validation, correct 4xx vs 5xx, no leaked stack traces/internals.
- Every request: structured JSON log line with request ID; log errors with context.
- API versioned under `/api/v1/`; `/health` stays fast and dependency-free.
- Type hints everywhere; small functions; readable > clever. No new deps without a defensible reason.
- Every endpoint/service function gets pytest coverage (happy path + failure/edge cases);
  prefer table-driven tests. Never make real network calls in tests — mock webhooks with respx.
- Small, frequent git commits with clear messages as work progresses.

## Domain invariants (do not regress these)
- **Ingestion durability**: persist the event AND enqueue its matching deliveries in ONE
  transaction before returning 202 — no "accepted but never fanned out" window.
- **Idempotent ingestion**: client-supplied event id deduped on the primary key
  (race-safe via IntegrityError catch); replays return 202 with `duplicate: true`.
- **Delivery semantics**: at-least-once per subscriber; subscribers dedupe on event id.
- **Webhooks**: httpx, 10s timeout (configurable), non-2xx and timeouts are failures; retry with
  exponential backoff + jitter up to MAX_DELIVERY_ATTEMPTS, then state=`failed` (dead-letter,
  queryable).
- **Audit**: append-only `delivery_attempts` row (timestamp, HTTP status, error) for EVERY attempt.
- **Filter rules**: declarative JSON (exact match on type/source + payload-path conditions);
  invalid rules rejected with 422 at subscription creation. Syntax documented in README.
- **Worker testability**: the fanout worker's single tick (`process_due_deliveries_once`) is a
  plain function tests call directly; the poll loop is just a thin wrapper around it.

## Workflow with AI assistants
- Propose a plan before multi-file changes; wait for approval.
- After changes: run `make lint && make test` and report results.
- If a requirement is ambiguous, state the assumption in the README rather than guessing silently.
