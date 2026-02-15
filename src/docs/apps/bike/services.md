# Bike Services (`apps/bike/services.py`)

## Scope
Provides BikeCode normalization/validation and delegates read/query behavior to bike managers, including list-filter orchestration for bike CRUD APIs.

## Execution Flows
- Normalize code (`normalize_bike_code`).
- Validate code format (`is_valid_bike_code`).
- Active-bike lookup via `Bike.domain.find_by_code` (`get_by_code`).
- Multi-stage suggestion via `Bike.domain.suggest_codes` (`suggest_codes`).
- List filter orchestration (`filter_bikes`) combining search/suggestion matching with state/date/ticket filters and ordering.

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
- Used by ticket intake typo-control flows and bike list search (`q`) filtering.

## Related Code
- `apps/bike/models.py`
- `apps/bike/managers.py`
- `api/v1/bike/views.py`
- `api/v1/ticket/serializers/ticket.py`
