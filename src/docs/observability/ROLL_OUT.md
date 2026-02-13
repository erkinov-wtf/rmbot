# Observability Rollout Plan

## Scope
This document tracks the production observability rollout for Rent Market:
- Error tracking (`Sentry`)

## Implemented Baseline (2026-02-13)
- Request correlation ID middleware enabled (`X-Request-ID`):
  - Incoming `X-Request-ID` is reused.
  - Missing ID is generated server-side and returned in response headers.
- Logging pipeline now includes `request_id` for console/file/telegram formats.
- Config-driven Sentry initialization added:
  - `DjangoIntegration` always when enabled.
  - `CeleryIntegration` when Celery is installed.
  - Runtime toggled by a valid `SENTRY_DSN` value.

## Environment Variables
- `SENTRY_DSN`
- `SENTRY_ENVIRONMENT`
- `SENTRY_RELEASE`
- `SENTRY_TRACES_SAMPLE_RATE`
- `SENTRY_PROFILES_SAMPLE_RATE`
- `SENTRY_SEND_DEFAULT_PII`

## Phase Plan
1. Phase 1: Error Tracking Stabilization
- Enable Sentry in staging with low sample rates.
- Verify grouped issues for API, Celery worker, and beat.
- Add release/version tagging in deployment pipeline (`SENTRY_RELEASE`).

2. Phase 2: Production Enablement
- Finalize production DSN and environment tagging discipline.
- Confirm event grouping quality and actionable issue triage paths.
- Document ownership and response workflow for critical errors.

## Rollout Checklist
- [ ] Staging Sentry enabled and validated
- [ ] Production Sentry enabled
- [ ] Sentry ownership/runbook documented
