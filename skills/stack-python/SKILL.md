---
name: stack-python
description: "Idiomatic Python backend implementation pack — project layout, framework idioms (FastAPI / Django / Flask), strict typing with mypy or pyright, pydantic v2 at boundaries, persistence (SQLAlchemy 2.0 / Django ORM), structured logging with structlog, async discipline, dependency management with uv or poetry, packaging (multi-stage Docker), and test idioms (pytest + pytest-asyncio + Testcontainers). Complements `engineering-standards/references/python.md` (the bar) with the implementation-side idioms (the playbook). Use whenever a developer is implementing a Python backend slice, scaffolding a new service, or choosing between framework patterns."
---

# Stack — Python

<!-- praxis:metadata:begin -->
```yaml
capability: stack
domain: backend
state: active
dependencies:
 - engineering-standards
triggers:
 - "implementing a feature on Python"
 - "scaffolding a new Python service"
 - "choosing between FastAPI / Django / Flask"
 - "configuring mypy / pyright strict"
 - "configuring Python testing"
outputs:
 - scaffolded module conforming to the layout
 - code conforming to standards + framework idioms
 - pyproject.toml + lock file (uv.lock or poetry.lock)
 - test scaffolds (pytest + Testcontainers)
consumers:
 - backend-developer
 - data-engineer
 - ml-ai-engineer
 - code-review
 - testing-strategy
references:
 - fastapi.md
 - django.md
 - flask.md
 - architecture.md
```
<!-- praxis:metadata:end -->

Implementation idioms for Python 3.11+ backend services. Complements `engineering-standards/references/python.md` — that file is the *bar*; this file is the *playbook*. Also applicable to data and ML codebases with the additional notes in the engineering-standards reference.

## Framework choice

| Framework | Sweet spot | Reference |
|---|---|---|
| **FastAPI** | API-first services, async-first, automatic OpenAPI from pydantic. Default for new projects in 2026. | `references/fastapi.md` |
| **Django** | Full-stack web with admin, ORM, migrations, auth built in. Sweet spot is data-heavy CRUD + admin. | `references/django.md` |
| **Flask** | Minimalist, mature; viable for small services. Less momentum than FastAPI. | `references/flask.md` |

Default: **FastAPI** unless the project's needs match Django or Flask specifically.

## Project layout

Bounded-context-first, mirrored from `engineering-standards`, using src-layout (not flat top-level — prevents accidental imports of test code and keeps editable installs clean). Load `references/architecture.md` for the full directory tree.

## Dependency management

`uv` (preferred — fast, modern, all-in-one) or `poetry`. Lock file checked in; pin Python via `.python-version` and `requires-python`. Load `references/architecture.md` for the full `pyproject.toml` template (deps, mypy strict, ruff, pytest config).

## Boundary validation with pydantic

Pydantic v2 at every external boundary — types are part of the model and validate on construction, so downstream code can trust them. Load `references/fastapi.md` (Pydantic v2 — the contract layer) for the request/response model pattern.

## Application service

Async-first. Constructor injection via `__init__`. Protocols (`typing.Protocol`) for the port interfaces. Load `references/architecture.md` for the full use-case template.

## Persistence — SQLAlchemy 2.0 (typed style)

Persistence tables are *separate* from domain entities. Migrations via **Alembic**, checked in. No `Base.metadata.create_all()` in production. Load `references/architecture.md` for the table + repository template.

## Logging

`structlog` for structured logging with contextvars. Correlation ID set at request boundary via middleware; propagated through async chains via `contextvars` automatically. Load `references/architecture.md` for the configuration snippet.

## Async discipline

- Don't mix sync and async carelessly. FastAPI handlers can be sync or async; async DB clients in sync handlers block the event loop — a blocker violation.
- `asyncio.gather(*tasks)` for independent parallel work; `asyncio.TaskGroup` (3.11+) for structured concurrency with proper cancellation semantics.
- Never blanket-catch `Exception` in an async function — it will swallow `CancelledError`. Catch specific types or let it propagate.

## Testing

pytest + pytest-asyncio + httpx + Testcontainers. Load `references/architecture.md` for the unit-test and Testcontainers fixture templates.

## Build and packaging

Multi-stage Dockerfile, distroless or `python:3.11-slim` base (or `poetry` equivalent). Pinned Python via the base image; ASGI server (`uvicorn` or `hypercorn`) for FastAPI; `gunicorn` + `uvicorn` workers in production. Load `references/architecture.md` for the Dockerfile.

## Observability hooks

- structlog for JSON logs with correlation ID (above).
- `prometheus-client` for metrics; `/metrics` endpoint.
- OpenTelemetry instrumentation can be added

## Sub-variant references

- `references/fastapi.md` — FastAPI patterns, dependency injection via `Depends`, async route handlers, lifespan management.
- `references/django.md` — Django patterns, isolating domain from `models.py`, async views, channels for real-time.
- `references/flask.md` — Flask patterns, application factory, blueprints, extensions discipline.
- `references/architecture.md` — framework-neutral templates: project layout, `pyproject.toml`, application service, SQLAlchemy persistence, structlog logging, pytest/Testcontainers, Dockerfile.

## Mode handling (G/B)

**Greenfield.** Scaffold via framework (`fastapi-cli`, `django-admin startproject`, or hand-rolled for Flask). Adopt the src-layout and bounded-context-first structure from the start.

**Brownfield.** Read `.repo-intel/conventions.md`. Match existing patterns for new code; flag drift in an ADR.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Python is dynamically typed; type hints are aspirational." | Type hints aren't aspirational — they're contracts that mypy / pyright check. Code without them ages worse. |
| "Async is faster." | Async is for I/O concurrency; CPU-bound code is slower in async. Pick the model the workload needs. |
| "Requirements.txt is fine." | Pin transitive dependencies via uv / poetry / pip-tools. `requirements.txt` without a lock is non-reproducible. |
| "Dataclasses are convenient; use them everywhere." | For data transfer use Pydantic for validation; for internal value objects use dataclasses; for ORM rows use ORM models. Different jobs. |
| "Notebooks are part of the codebase." | Notebooks are for exploration. Production-bound logic moves to `src/`; notebooks become artifacts of analysis only. |
| "We'll switch to Rust / Go later if performance matters." | Premature. Profile first; optimize the bottleneck. Most "Python is slow" claims are actually "this code is slow." |

## Verification

You are done when:

- [ ] Type hints on all public functions; mypy / pyright runs clean.
- [ ] Dependency management via `pyproject.toml` + lockfile (uv / poetry).
- [ ] Virtual environment is reproducible (lock + Python version pinned).
- [ ] Linter (ruff / pylint) + formatter (ruff format / black) enforced in CI.
- [ ] Logging via `logging` module with structured handlers; not `print`.
- [ ] Pytest fixtures + parametrize used appropriately.
- [ ] Pydantic models at API boundaries.
- [ ] Brownfield: existing conventions matched; divergence captured in ADR.

Evidence to check:
- `python -m mypy .` runs clean.
- `python -m ruff check .` runs clean.
- Lockfile reproduces the same versions on different machines.

## Anti-patterns

- Untyped function signatures in production code.
- `from module import *`.
- Bare `except:` or `except Exception:` outside the outermost handler.
- Mutable default arguments (`def foo(items=[]):`).
- Sync DB clients in async handlers (blocks the event loop).
- `print()` in production code.
- Global mutable state outside explicit config/singleton.
- Importing from `infrastructure` into `domain` (dependency-inversion violation).
