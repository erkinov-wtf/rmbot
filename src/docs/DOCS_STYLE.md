# Documentation Style Guide

## Purpose
Provide one consistent, technical structure for source docs under `src/docs/` so onboarding and incident lookup are fast.

## Global Rules
- Mirror code paths where practical.
- Keep content technical and behavior-focused.
- Prefer concrete contracts and invariants over narrative prose.
- Keep docs updated in the same session/PR as code behavior changes.

## Required Sections by Doc Type

### Index docs (`README.md` in module folders)
- `Scope`
- `Navigation`
- `Maintenance Rules`
- `Related Code` (or `Related Docs` for cross-index pointers)

### Service docs (`services.md` / `services_*.md`)
- `Scope`
- `Execution Flows`
- `Invariants and Contracts`
- `Side Effects`
- `Failure Modes`
- `Operational Notes`
- `Related Code`

### Model docs (`models.md`)
- `Scope`
- `Model Inventory`
- `Invariants and Constraints`
- `Lifecycle Notes`
- `Operational Notes`
- `Related Code`

### API domain docs (`docs/api/v1/<domain>/README.md`)
- `Scope`
- `Access Model`
- `Endpoint Reference` (method + path + technical behavior)
- `Validation and Failure Modes`
- `Operational Notes`
- `Related Code`

## Writing Quality Bar
- Describe what changes state and why.
- Explicitly mention role checks, idempotency keys, and append-only behavior where applicable.
- Call out non-obvious side effects and data coupling.
