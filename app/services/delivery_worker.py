from sqlalchemy.orm import Session

# TODO(iteration 2 — fanout worker): DB-backed delivery queue.
#
# Design (keep the tick injectable so tests drive it deterministically):
#
#   def process_due_deliveries_once(session: Session, client: httpx.AsyncClient) -> int:
#       - select deliveries WHERE state='pending' AND next_attempt_at <= now
#       - POST event payload to the subscription url (settings.webhook_timeout_s)
#       - append a DeliveryAttempt row for EVERY attempt (http status or error)
#       - 2xx -> state='delivered'
#       - failure -> attempt_count += 1; exponential backoff + jitter on next_attempt_at;
#         after settings.max_delivery_attempts -> state='failed' (dead-letter, queryable)
#       - returns number of deliveries processed
#
#   async def run_loop() -> None:
#       - started from the app lifespan; sleeps settings.worker_poll_interval_s
#         between ticks; never crashes the app (log and continue)
#
# Tests mock all webhook HTTP with respx: success, 500-then-success, timeout,
# permanent failure -> failed state. No real network calls.


def process_due_deliveries_once(session: Session) -> int:
    """Single worker tick. Not implemented in iteration 1 (no fanout yet)."""
    raise NotImplementedError("fanout worker lands in iteration 2")
