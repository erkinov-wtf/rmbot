# Bike Managers (`apps/bike/managers.py`)

## Scope
Encapsulates bike domain queries so service and analytics layers reuse the same alive-only lookup rules.

## Manager Inventory
- `BikeQuerySet`: composable filters (`active_fleet`, `ready`, `by_code`, search/date/state filters, active-ticket filters).
- `BikeDomainManager`: alive-only queryset plus helper methods for lookup/suggestions.

## Execution Notes
- `find_by_code` resolves case-insensitive BikeCode lookup against non-deleted bikes.
- `ready_active_count` centralizes stockout/availability count logic.
- `suggest_codes` executes staged lookup (prefix -> contains -> fuzzy) with bounded results.
- QuerySet helpers support bike list filtering by code/status/activity/date windows and active-ticket presence.

## Invariants and Contracts
- `get_queryset` enforces `deleted_at IS NULL`.
- Suggestion output is deduplicated and capped by caller-provided limit.

## Related Code
- `apps/bike/models.py`
- `apps/bike/services.py`
- `apps/ticket/services_stockout.py`
