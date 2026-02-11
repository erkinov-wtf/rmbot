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

Run tests with pytest:
```
uv run pytest
```

Coverage outputs:
- Terminal report (missing lines)
- `coverage.xml` (CI integrations)
- `htmlcov/index.html` (HTML report)
