from fastapi import APIRouter

router = APIRouter(prefix="/deliveries", tags=["deliveries"])

# TODO(iteration 2 — audit): delivery state + audit endpoints:
#   GET /api/v1/deliveries?event_id=... | ?subscription_id=...   delivery state per fanout
#   GET /api/v1/deliveries/{id}/attempts                         attempt history: timestamp,
#                                                                http status, error, final state
# Read-only queries over deliveries + delivery_attempts (append-only audit table).
