# Rent Market

## Project Documentation
- Product and business spec: `PROJECT.md`
- Engineering and implementation memory: `AGENTS.md`
- Deployment secrets/setup: `docs/deployment/GITHUB-SECRETS.md`

## Quick Test Run
```
LOGS_ROOT=./logs TEST_DATABASE_URL=sqlite:///:memory: python src/manage.py test tests
```

## Pytest + Coverage
Install dev dependencies first:
```
uv sync --group dev
```

## Black + Ruff via pre-commit
Install git hooks:
```
uv run pre-commit install
```

Run hooks on all files:
```
uv run pre-commit run --all-files
```

## API Docs (Swagger/OpenAPI)
After installing dependencies and running the server, docs are available at:
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI schema: `/api/schema/`

Access onboarding note:
- New access requests are submitted through Telegram bot `/start` onboarding only.
- Managers approve/reject via `/api/v1/users/access-requests/{id}/approve|reject/`.

Run tests with pytest:
```
uv run pytest
```

Coverage outputs:
- Terminal report (missing lines)
- `coverage.xml` (CI integrations)
- `htmlcov/index.html` (HTML report)
