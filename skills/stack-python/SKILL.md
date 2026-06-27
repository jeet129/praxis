---
name: stack-python
description: Idiomatic Python backend implementation pack — project layout, framework idioms (FastAPI / Django / Flask), strict typing with mypy or pyright, pydantic v2 at boundaries, persistence (SQLAlchemy 2.0 / Django ORM), structured logging with structlog, async discipline, dependency management with uv or poetry, packaging (multi-stage Docker), and test idioms (pytest + pytest-asyncio + Testcontainers). Complements `engineering-standards/references/python.md` (the bar) with the implementation-side idioms (the playbook). Use whenever a developer is implementing a Python backend slice, scaffolding a new service, or choosing between framework patterns.
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

Bounded-context-first, mirrored from `engineering-standards`, using src-layout:

```
src/product/
├── billing/
│ ├── domain/
│ │ ├── __init__.py
│ │ ├── order.py aggregate
│ │ ├── order_id.py value object
│ │ ├── order_repository.py protocol
│ │ └── events/order_placed.py domain event
│ ├── application/
│ │ ├── __init__.py
│ │ ├── place_order.py use case
│ │ └── ports/payment_gateway.py protocol
│ ├── infrastructure/
│ │ ├── persistence/
│ │ │ ├── sqlalchemy_order_repository.py adapter
│ │ │ └── order_table.py ORM table
│ │ └── external/stripe_payment_gateway.py
│ └── presentation/
│ ├── __init__.py
│ ├── orders_router.py FastAPI router
│ ├── order_request.py pydantic model
│ └── order_response.py pydantic model
├── auth/
│ └── ...
└── shared/ default empty

tests/ mirrors src/
```

src-layout (not flat top-level) prevents accidental imports of test code and keeps editable installs clean.

## Dependency management

`uv` (preferred — fast, modern, all-in-one) or `poetry`. Lock file checked in.

```toml
# pyproject.toml
[project]
name = "product"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
 "fastapi>=0.115",
 "pydantic>=2.7",
 "sqlalchemy>=2.0",
 "alembic>=1.13",
 "structlog>=24.0",
 "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
 "pytest>=8.0",
 "pytest-asyncio>=0.23",
 "pytest-cov>=5.0",
 "mypy>=1.10",
 "ruff>=0.4",
 "testcontainers>=4.0",
]

[tool.mypy]
strict = true
python_version = "3.11"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "PT", "RUF"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Pin Python via `.python-version` and `requires-python`.

## Boundary validation with pydantic

Pydantic v2 at every external boundary. Types are part of the model:

```python
# billing/presentation/order_request.py
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator

class LineItem(BaseModel):
 sku: str = Field(min_length=1, max_length=64)
 quantity: int = Field(gt=0)

class OrderRequest(BaseModel):
 customer_id: str = Field(min_length=1, max_length=100)
 amount: Decimal = Field(gt=Decimal("0.00"))
 items: list[LineItem] = Field(min_length=1)

 @field_validator("amount")
 @classmethod
 def amount_has_two_decimals(cls, v: Decimal) -> Decimal:
 if v.as_tuple().exponent < -2:
 raise ValueError("amount must have at most two decimal places")
 return v
```

Pydantic validates on construction; downstream code can trust the types.

## Application service

```python
# billing/application/place_order.py
from dataclasses import dataclass
from decimal import Decimal

from product.billing.application.ports.payment_gateway import PaymentGateway
from product.billing.domain.order import Order
from product.billing.domain.order_id import OrderId
from product.billing.domain.order_repository import OrderRepository
from product.shared.events.event_bus import EventBus


@dataclass(frozen=True, slots=True)
class PlaceOrderCommand:
 customer_id: str
 amount: Decimal


class PlaceOrderUseCase:
 def __init__(
 self,
 orders: OrderRepository,
 payments: PaymentGateway,
 events: EventBus,
 ) -> None:
 self._orders = orders
 self._payments = payments
 self._events = events

 async def execute(self, cmd: PlaceOrderCommand) -> OrderId:
 order = Order.place(customer_id=cmd.customer_id, amount=cmd.amount)
 await self._orders.save(order)
 await self._payments.charge(order.id, cmd.amount)
 await self._events.publish(order.placed_event())
 return order.id
```

Async-first. Constructor injection via `__init__`. Protocols (`typing.Protocol`) for the port interfaces.

## Persistence — SQLAlchemy 2.0 (typed style)

Persistence tables are *separate* from domain entities:

```python
# billing/infrastructure/persistence/order_table.py
from decimal import Decimal
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): ...

class OrderTable(Base):
 __tablename__ = "orders"
 id: Mapped[str] = mapped_column(primary_key=True)
 customer_id: Mapped[str] = mapped_column(index=True)
 amount: Mapped[Decimal]
 status: Mapped[str]


# billing/infrastructure/persistence/sqlalchemy_order_repository.py
from sqlalchemy.ext.asyncio import AsyncSession

from product.billing.domain.order import Order
from product.billing.domain.order_id import OrderId
from product.billing.domain.order_repository import OrderRepository
from .order_table import OrderTable


class SqlAlchemyOrderRepository(OrderRepository):
 def __init__(self, session: AsyncSession) -> None:
 self._session = session

 async def save(self, order: Order) -> None:
 row = OrderTable(id=order.id.value, customer_id=order.customer_id, amount=order.amount, status=order.status.value)
 await self._session.merge(row)

 async def find(self, id: OrderId) -> Order | None:
 row = await self._session.get(OrderTable, id.value)
 return Order.reconstitute(row) if row else None
```

Migrations via **Alembic**, checked in. No `Base.metadata.create_all()` in production.

## Logging

`structlog` for structured logging with contextvars:

```python
import structlog
import contextvars

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

def _add_correlation(_, __, event_dict):
 event_dict["correlation_id"] = correlation_id.get()
 return event_dict

structlog.configure(
 processors=[
 structlog.stdlib.add_log_level,
 _add_correlation,
 structlog.processors.TimeStamper(fmt="iso"),
 structlog.processors.JSONRenderer(),
 ],
 wrapper_class=structlog.stdlib.BoundLogger,
)

log = structlog.get_logger()
```

Correlation ID set at request boundary via middleware; propagated through async chains via `contextvars` automatically.

## Async discipline

- Don't mix sync and async carelessly. FastAPI handlers can be sync or async; async DB clients in sync handlers block the event loop — a blocker violation.
- `asyncio.gather(*tasks)` for independent parallel work; `asyncio.TaskGroup` (3.11+) for structured concurrency with proper cancellation semantics.
- Never blanket-catch `Exception` in an async function — it will swallow `CancelledError`. Catch specific types or let it propagate.

## Testing

pytest + pytest-asyncio + httpx + Testcontainers:

```python
# tests/billing/application/test_place_order.py
import pytest
from decimal import Decimal

from product.billing.application.place_order import PlaceOrderUseCase, PlaceOrderCommand
from tests.fakes.in_memory_order_repository import InMemoryOrderRepository
from tests.fakes.stub_payment_gateway import StubPaymentGateway
from tests.fakes.stub_event_bus import StubEventBus


@pytest.fixture
def use_case() -> PlaceOrderUseCase:
 return PlaceOrderUseCase(
 orders=InMemoryOrderRepository(),
 payments=StubPaymentGateway(),
 events=StubEventBus(),
 )


@pytest.mark.asyncio
async def test_place_order_persists_and_returns_id(use_case: PlaceOrderUseCase) -> None:
 cmd = PlaceOrderCommand(customer_id="cust-1", amount=Decimal("50.00"))
 order_id = await use_case.execute(cmd)
 assert order_id is not None
```

Integration tests with Testcontainers:

```python
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres() -> str:
 with PostgresContainer("postgres:16-alpine") as pg:
 yield pg.get_connection_url()
```

## Build and packaging

Multi-stage Dockerfile, distroless or `python:3.11-slim` base:

```dockerfile
FROM python:3.11-slim AS build
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY src ./src

FROM gcr.io/distroless/python3-debian12:nonroot
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
ENV PATH="/app/.venv/bin:$PATH"
USER nonroot
CMD ["python", "-m", "product.main"]
```

Or `poetry` equivalent. Pinned Python via the base image; ASGI server (`uvicorn` or `hypercorn`) for FastAPI; `gunicorn` + `uvicorn` workers in production.

## Observability hooks 

- structlog for JSON logs with correlation ID (above).
- `prometheus-client` for metrics; `/metrics` endpoint.
- OpenTelemetry instrumentation can be added

## Sub-variant references

- `references/fastapi.md` — FastAPI patterns, dependency injection via `Depends`, async route handlers, lifespan management.
- `references/django.md` — Django patterns, isolating domain from `models.py`, async views, channels for real-time.
- `references/flask.md` — Flask patterns, application factory, blueprints, extensions discipline.

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
