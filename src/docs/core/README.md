# Core Docs Index

## Scope
Documents shared platform behavior used across all apps: base models, API envelopes, permissions, and security helpers.

## Navigation
- `docs/core/models_and_deletion.md`
- `docs/core/api/README.md`
- `docs/core/utils/README.md`
- `docs/core/notifications.md`
- `docs/core/management/commands/generate_mock_data.md`

## Maintenance Rules
- Keep core docs current when changing shared contracts used by multiple apps.
- Treat response envelope, deletion, and append-only behavior as high-impact documentation areas.

## Related Code
- `core/models.py`
- `core/api/`
- `core/middlewares/`
- `core/utils/`
- `core/services/notifications.py`
