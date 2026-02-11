# PROGRESS.md

## Purpose
Track delivery progress across sessions against `PROJECT.md`.

How to use this file:
- Mark completed items as `[x]`.
- Keep currently active work as `[~]`.
- Keep not-started work as `[ ]`.
- Add sub-tasks only when implementation begins.
- Add one short note under **Session Notes** at the end of each meaningful session.

Status legend:
- `[x]` Done
- `[~]` In progress / partially implemented
- `[ ]` Not started

## Delivery Roadmap

### Phase A - Core operations (RBAC, tickets, timer, QC, basic XP)
- `[x]` Onboarding + RBAC foundation
  - `[x]` Roles model and role-based DRF permission (`HasRole`)
  - `[x]` Access request flow (`request-access`) and moderation (`approve/reject`)
  - `[x]` Telegram profile linking on approval
- `[x]` Ticket and bike operational baseline
  - `[x]` Bike domain + API list/create
  - `[x]` Ticket domain + lifecycle actions (`create/assign/start/to-waiting-qc/qc-pass/qc-fail`)
  - `[x]` Workflow transition audit (`TicketTransition`) and transitions list endpoint
- `[x]` Work timer (`work_sessions`)
  - `[x]` `start/pause/resume/stop`
  - `[x]` open-session uniqueness constraints (ticket + technician)
- `[x]` Attendance baseline
  - `[x]` `checkin/checkout/today`
  - `[x]` punctuality XP entry on check-in
- `[~]` Ticket intake completeness
  - `[ ]` Checklist snapshot/tasks (>=10) enforced in ticket intake
  - `[ ]` SRT approval flow details (Master-driven)
  - `[ ]` BikeCode typo control + confirm-create flow

### Phase B - Gamification + payroll caps + level-up jobs
- `[~]` XP ledger baseline
  - `[x]` XP entries on attendance + QC PASS (base + first-pass bonus)
  - `[x]` Append-only protections (`XPLedger` and `TicketTransition`)
  - `[x]` XP ledger read API (`GET /api/v1/xp/ledger/`) with role-aware filtering
- `[ ]` Progression/levels engine
  - `[ ]` Raw XP to level mapping
  - `[ ]` Weekly level evaluation job
  - `[ ]` Coupon event issuance flow
- `[ ]` Paid XP and payroll
  - `[ ]` Paid XP caps by level (L1-L5)
  - `[ ]` Payroll monthly snapshot model/service
  - `[ ]` `POST /payroll/{month}/close`
  - `[ ]` `POST /payroll/{month}/approve`
  - `[ ]` Payroll projection validation tests

### Phase C - BI dashboard + rules studio + rollback
- `[ ]` Dynamic rules engine (versioned)
  - `[ ]` Rules config storage and version history
  - `[ ]` Diff + rollback support
  - `[ ]` Cache bust strategy for active rules
- `[ ]` Analytics APIs
  - `[ ]` `GET /analytics/fleet`
  - `[ ]` `GET /analytics/team`
  - `[ ]` backlog/SLA/QC KPI datasets

### Phase D - SLA automation + stockout incidents + allowance gating
- `[ ]` Stockout incident detector (10:00-20:00 Asia/Tashkent)
- `[ ]` SLA automation rules/actions
- `[ ]` Allowance gating tied to level/SLA thresholds

## Cross-cutting Engineering Work
- `[~]` Security hardening
  - `[x]` TMA `initData` verification endpoint implemented
  - `[x]` Webhook secret validation in bot webhook endpoint
  - `[ ]` Final review of auth-date expiry window and replay protections
- `[ ]` Infrastructure parity with target architecture
  - `[ ]` Redis integration
  - `[ ]` Worker/job runner integration (Celery-compatible)
- `[ ]` Observability stack
  - `[ ]` OpenTelemetry traces
  - `[ ]` Prometheus/Grafana metrics
  - `[ ]` Sentry integration
- `[ ]` Deployment/runtime cleanup
  - `[ ]` Healthcheck script path alignment (`/api/v1/misc/health/`)
  - `[ ]` Revisit `makemigrations` in startup flow for production discipline

## Testing Progress
- `[x]` Integration tests for implemented API slices (account/auth/attendance/bike/ticket/xp/audit feed)
- `[x]` Unit tests for Telegram verification and append-only protections
- `[ ]` E2E flow with Telegram Mini App context (Master -> Technician -> QC)
- `[ ]` Load and security test scenarios for webhook/RBAC bypass attempts

## Immediate Next Steps (Priority)
1. Implement payroll domain (`payroll_monthly`) + close/approve endpoints with tests.
2. Implement paid XP cap calculations (L1-L5) used by payroll projection.
3. Add rules versioning module so XP/payroll formulas are DB-configurable.
4. Complete ticket intake checklist/SRT validation requirements.
5. Add analytics fleet/team endpoints and KPI aggregation services.

## Session Notes
- `2026-02-11`: Phase A baseline is largely implemented (RBAC, ticket lifecycle, work sessions, attendance, QC-linked XP, audit feed). Added XP ledger API and append-only protections; full test suite passing.
