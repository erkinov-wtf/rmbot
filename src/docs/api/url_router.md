# API Root Router (`api/url_router.py`)

## Scope
Defines top-level API URL composition and optional OpenAPI docs endpoints.

## Execution Flow
1. Registers version routes under `/api/v1/`.
2. Attempts to import `drf-spectacular`.
3. If available, prepends `/api/schema/`, `/api/docs/`, `/api/redoc/` routes.

## Invariants and Contracts
- `/api/v1/` remains the canonical version root.
- Docs routes exist only when `drf-spectacular` package is installed.

## Failure Modes
- Missing `drf-spectacular` does not break API routing; only docs endpoints are skipped.

## Related Code
- `api/url_router.py`
- `config/urls/base.py`
