# Telegram Security Utilities

## Scope
Documents Telegram Mini App `init_data` cryptographic verification and freshness validation helpers.

## Validation Flow (`validate_init_data`)
1. Parse incoming `init_data` query string.
2. Build Telegram data-check string from sorted key/value pairs.
3. Derive expected HMAC key (`WebAppData` flow) and compute expected hash.
4. Compare provided and expected hashes with constant-time comparison.
5. Validate `auth_date` for max age and future skew limits.

## Invariants and Contracts
- Hash comparison is constant-time to reduce timing leak risk.
- `auth_date` must be parseable and within configured window.
- Helper returns only after full integrity and freshness checks pass.

## Helper Contract
- `extract_init_data_hash` returns hash token used by replay-lock logic.
- Replay protection is performed at API/service layer using cache-based one-time lock.

## Failure Modes
- Malformed query string, missing hash, invalid signature, stale/future timestamp -> `InitDataValidationError`.
- API layer maps validation failure to `400` user-safe responses.

## Operational Notes
- Treat `init_data` as one-time proof; never accept client-decoded user payload without verification.
- Keep skew/ttl values environment-controlled for security posture tuning.

## Related Code
- `core/utils/telegram.py`
- `api/v1/core/views/auth.py`
