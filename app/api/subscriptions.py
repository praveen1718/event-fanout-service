from fastapi import APIRouter

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# TODO(iteration 2 — subscriptions): implement without restart:
#   POST   /api/v1/subscriptions        create (validate url + filter rules, invalid rules -> 422)
#   GET    /api/v1/subscriptions        list
#   DELETE /api/v1/subscriptions/{id}   delete (soft-delete via `active` flag so past
#                                       deliveries keep their audit trail)
# Backed by app/services/subscriptions.py + app/repositories/subscriptions.py.
