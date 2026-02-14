# Bike Services (`apps/bike/services.py`)

## Scope
Provides BikeCode normalization, validation, lookup, and suggestion capabilities.

## Execution Flows
- Normalize code (`normalize_bike_code`).
- Validate code format (`is_valid_bike_code`).
- Active-bike lookup (`get_by_code`).
- Multi-stage suggestion (`suggest_codes`).

## Invariants and Contracts
- Canonical BikeCode normalization is uppercase without whitespace.
- Format regex is strictly enforced.
- Suggestions are capped and deterministic by query strategy.

## Side Effects
- No write side effects; read-only service.

## Failure Modes
- Invalid code format at caller validation layer.
- Short suggestion query yields empty result.

## Operational Notes
- Suggestion strategy: prefix -> contains -> fuzzy.
- Used by ticket intake typo-control flows.

## Related Code
- `apps/bike/models.py`
- `api/v1/bike/views.py`
- `api/v1/ticket/serializers/ticket.py`
