# Logging Utilities

## Scope
Documents request-context enrichment and Telegram error-delivery behavior for centralized logging utilities.

## Request Context Filter (`RequestContextFilter`)
1. Reads `record.request` from incoming log records.
2. Applies request metadata only when object shape matches HTTP request fields (`method`, `path`, `META`).
3. Falls back to safe defaults (`Unknown`, `-`) for non-request records.
4. Appends formatted traceback text when `exc_info` is present.

## Invariants and Contracts
- Filter must never raise during logging, including for Django devserver socket-based records.
- Formatter-required fields (`user`, `method`, `path`, `ip`, `request_id`, `traceback`) are always set.
- Non-HTTP records are treated as contextless logs and stay process-safe.

## Telegram Error Handler (`TelegramErrorHandler`)
1. Formats log records and strips inline `exc_info` duplication.
2. Queues outbound messages to avoid blocking request threads.
3. Sends batched queue entries to Telegram Bot API in a background worker thread.

## Failure Modes
- Telegram delivery/network failures are swallowed to avoid interrupting application runtime.
- Full queue drops new messages silently to protect service availability.

## Operational Notes
- Keep log formatters aligned with fields populated by `RequestContextFilter`.
- Use environment-based Telegram credentials; empty credentials effectively disable delivery.

## Related Code
- `core/utils/logging.py`
- `config/settings/base.py`
