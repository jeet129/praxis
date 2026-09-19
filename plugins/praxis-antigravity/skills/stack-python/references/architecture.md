# Reference — Architecture, persistence, logging, testing & packaging (Python)

Loaded by `stack-python` for the framework-neutral implementation templates that apply regardless of which of FastAPI / Django / Flask was chosen. Framework-specific idioms live in `fastapi.md`, `django.md`, `flask.md`.

## Project layout

Bounded-context-first, mirrored from `engineering-standards`, using src-layout:

```
src/product/
├── billing/
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── order.py                 aggregate
│   │   ├── order_id.py              value object
│   │   ├── order_repository.py      protocol
│   │   └── events/order_placed.py   domain event
│   ├── application/
│   │   ├── __init__.py
│   │   ├── place_order.py           use case
│   │   └── ports/payment_gateway.py protocol
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── sqlalchemy_order_repository.py   adapter
│   │   │   └── order_table.py                   ORM table
│   │   └── external/stripe_payment_gateway.py
│   └── presentation/
│       ├── __init__.py
│       ├── orders_router.py     FastAPI router
│       ├── order_request.py     pydantic model
│       └── order_response.py    pydantic model
├── auth/
│   └── ...
└── shared/                      default empty

tests/ mirrors src/
```

src-layout (not flat top-level) prevents accidental imports of test code and keeps editable installs clean.

## Dependency management — `pyproject.toml`

`uv` (preferred — fast, modern, all-in-one) or `poetry`. Lock file checked in. Pin Python via `.python-version` and `requires-python`.

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

## Application service

Async-first. Constructor injection via `__init__`. Protocols (`typing.Protocol`) for the port interfaces.

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

## Persistence — SQLAlchemy 2.0 (typed style)

Persistence tables are *separate* from domain entities. Migrations via **Alembic**, checked in. No `Base.metadata.create_all()` in production.

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

## Logging — structlog with correlation IDs

Correlation ID set at request boundary via middleware; propagated through async chains via `contextvars` automatically.

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

## Testing — pytest + pytest-asyncio + Testcontainers

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

Multi-stage Dockerfile, distroless or `python:3.11-slim` base. Pinned Python via the base image; ASGI server (`uvicorn` or `hypercorn`) for FastAPI; `gunicorn` + `uvicorn` workers in production.

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

Or `poetry` equivalent.
