# Engineering Standards — Python

Stack-specific expression of the principles in `SKILL.md` for Python 3.11+. Backend services (FastAPI / Django / Flask), data pipelines (Airflow / Dagster / Prefect), and ML codebases.

## Project layout

Bounded contexts as top-level packages, not technical layers:

```
src/product/
├── billing/
│   ├── domain/             entities, value objects, domain events
│   ├── application/        use cases, services, ports
│   ├── infrastructure/     adapters (repositories, external clients)
│   └── presentation/       FastAPI routers / Django views / Flask blueprints
├── auth/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── presentation/
└── shared/                 cross-cutting only; default empty
    ├── common/
    └── events/

tests/                      mirrors src/ structure
```

`src/` layout (rather than flat top-level package) prevents accidental imports of test code and keeps editable installs clean. `models.py` + `views.py` + `forms.py` at the root is a Django-template violation for non-trivial projects.

## Type hints

Type hints are not optional in this codebase. `strict` mypy or pyright settings are the baseline.

`pyproject.toml`:
```toml
[tool.mypy]
strict = true
python_version = "3.11"
warn_redundant_casts = true
warn_unused_ignores = true
disallow_any_explicit = true
```

Untyped Python code is acceptable only in scripts under `scripts/` and notebook prototypes — never in production paths.

## Naming

- Modules: `snake_case.py`. `user_service.py`, not `userService.py`.
- Classes: `PascalCase`.
- Functions and variables: `snake_case`.
- Constants: `SCREAMING_SNAKE_CASE`.
- Booleans: `is_active`, `has_permission`, `can_retry`.
- Private names: leading underscore (`_internal`). Dunder names (`__name__`) for the language's own conventions, not for "really private."

## SOLID applied

**S — Single responsibility.** A module has one reason to change. The Django `views.py` god-file pattern is a classic violation; split into per-resource modules.

**O — Open/closed.** Protocols (`typing.Protocol`) or abstract base classes (`abc.ABC`) for variation points. Strategy pattern via injected callables is also idiomatic Python.

**L — Liskov.** Subclasses honor parent contracts. The async/sync trap is the most common Python LSP violation — never override a sync method with an async one; refactor the parent or use a separate async hierarchy.

**I — Interface segregation.** Small Protocols over large abstract bases. `class OrderReader(Protocol): def get_order(self, id: OrderId) -> Order: ...` is preferable to a 30-method `OrderRepository`.

**D — Dependency inversion.** Ports as Protocols in `domain/`; adapters in `infrastructure/`. Composition root in `presentation/app_factory.py` or equivalent wires everything.

## Data classes and immutability

- Use `pydantic.BaseModel` (v2) for boundary types (API requests/responses, config) — gives runtime validation + type hints in one shot.
- Use `@dataclass(frozen=True, slots=True)` for domain value objects. `frozen=True` makes them immutable; `slots=True` is a memory + performance win.
- Use `attrs` only if you have a specific need pydantic + dataclass don't cover (rare).

## Error handling

- Domain errors are typed exceptions inheriting from a project-base `DomainError`.
- Infrastructure errors (HTTPException, DBError, etc.) get translated at the application service boundary to domain errors.
- `try/except Exception` is a violation; catch narrow.
- `return None` to signal absence is a violation in typed code; return `Optional[T]` with the type explicit.
- Logging exception with `logger.exception()` (which captures the traceback) at the boundary where it's handled — not at every layer.

## Validation

- Pydantic v2 at the API boundary. Request models, response models, config models all defined as `BaseModel` subclasses with field validators where needed.
- Domain invariants in `__post_init__` for dataclasses, or `model_validator(mode='after')` for pydantic models. Invalid state should be unconstructable.

## Async

- FastAPI and modern frameworks are async-first. Don't mix sync and async carelessly — calling sync DB clients inside async handlers blocks the event loop.
- `asyncio.gather(*tasks)` for independent parallel work; `asyncio.TaskGroup` (3.11+) for structured concurrency.
- Cancellation via `asyncio.CancelledError`; propagate it. Never blanket `except Exception:` that catches `CancelledError`.

## Persistence

- SQLAlchemy 2.0 (the new typed style) for typed ORM access; or raw SQL via psycopg if the codebase prefers it.
- Alembic for migrations, checked into the repo. No `Base.metadata.create_all()` in production.
- For Django projects: keep the ORM but isolate domain logic from `models.py`. Domain entities are *not* Django models; Django models live in `infrastructure/persistence/` and are mapped.
- For data work: pandas → polars when projects scale; pyspark for genuinely big data.

## Logging

- `structlog` for structured logging; or stdlib `logging` with a JSON formatter.
- Correlation ID via `contextvars` — set at request boundary, propagated automatically through async context.
- Never log raw request/response bodies that may carry PII.

## Dependency management & build

- `uv` (preferred) or `poetry` for dependency management; pinned lock file checked in.
- `pyproject.toml` is the single source of truth. No `requirements.txt` unless required by deployment tooling — and if so, generate from the lock file in CI.
- Pin Python version via `.python-version` and `pyproject.toml` `requires-python`.
- Production Dockerfile: multi-stage build, distroless or `python:3.11-slim` base, non-root user.

## Testing

- `pytest` + `pytest-asyncio` for async tests.
- `httpx` test client for FastAPI; `django.test` for Django.
- Testcontainers (`testcontainers` PyPI package) for real Postgres / Redis in integration tests — never SQLite as a Postgres substitute.
- Tests mirror source layout: `tests/billing/test_user_service.py` next to `src/product/billing/application/user_service.py`.
- Test names: descriptive. `def test_charge_tenant_with_insufficient_credit_raises_error()`. Or `pytest-describe` style if the team prefers nested describe blocks.

## Common violations to flag in review

- Untyped function signatures in production code.
- `from module import *` (use explicit imports).
- Bare `except:` or `except Exception:` outside the outermost handler.
- Mutable default arguments (`def foo(items=[]):` — classic Python footgun).
- Class methods that should be module functions (Java-mind violation — Python doesn't need a class for every behavior).
- Comparing with `==` when `is` is meant, or vice versa (especially for `None`).
- `print()` in production code paths.
- Global mutable state outside explicit config or singleton patterns.

## ML / data-engineering specifics (when applicable)

When this stack is being used for ML or data work, additional discipline:

- `pyproject.toml` declares ML dependencies (`torch`, `numpy`, `pandas` / `polars`, `scikit-learn`) with constrained version ranges — not bare `torch`. Reproducibility matters.
- Notebooks (`*.ipynb`) live in `notebooks/` and are for exploration only. Anything to be promoted is migrated to a `*.py` module before merge.
- Random seeds set at every entry point that uses randomness. Reproducibility is a discipline, not a hope.
- Data file paths never hard-coded; use config + environment.

## Tooling

Recommended baseline:

- **Package manager:** `uv` (fast, modern) or `poetry`.
- **Test:** pytest, pytest-asyncio, pytest-cov, httpx (for FastAPI), Testcontainers.
- **Type checking:** mypy (strict) or pyright. Run in CI.
- **Lint:** ruff (replaces flake8 + isort + many others; fast).
- **Format:** ruff format (or Black if the project predates ruff format).
- **Security:** `bandit` for SAST; `pip-audit` for known CVEs; `safety` as a secondary check.
