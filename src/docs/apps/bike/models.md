# Bike Models (`apps/bike/models.py`)

## Scope
Defines fleet bike entity used by ticket intake and availability metrics.

## Model Inventory
- `Bike`: bike code, status, and active flag.

## Invariants and Constraints
- `bike_code` is unique.
- Status/activity indexed for fleet analytics and stockout detection queries.

## Lifecycle Notes
- Bikes may be created via admin/API or intake confirm-create path.
- Bike status transitions now expose model-level helpers (`mark_in_service`, `mark_ready`) so workflow services do not mutate status fields directly.

## Operational Notes
- Write-off bikes are excluded from active-availability computations.
- Query-focused access goes through `Bike.domain` manager methods for alive-only lookup and fleet counters.

## Related Code
- `apps/bike/services.py`
- `apps/bike/managers.py`
- `api/v1/bike/views.py`
- `apps/ticket/services_stockout.py`
