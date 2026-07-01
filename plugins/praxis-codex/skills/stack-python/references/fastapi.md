# Reference — FastAPI (Python)

Loaded by `stack-python` when FastAPI is the chosen HTTP framework.

## When to use

FastAPI is the recommended default for new Python APIs when:
- You want type-driven validation + automatic OpenAPI docs from Pydantic models.
- Async I/O matters (FastAPI is async-native).
- You're comfortable with async/await as the default.

Skip FastAPI when:
- The team is heavily invested in Django + ORM and the API is a side concern.
- You need Django-style admin UI / ORM tight integration → Django (`django.md`).
- The project is a microservice with no Python-specific reason → consider Node/TS.

## Project layout

```
src/
├── main.py                 wire-up; creates the FastAPI app
├── config.py               settings via pydantic-settings
├── deps.py                 shared Depends() factories (DB session, auth, etc.)
├── routers/                route modules per resource
│   ├── orders.py
│   └── users.py
├── schemas/                Pydantic models (request/response)
│   ├── order.py
│   └── user.py
├── services/               business logic (no FastAPI dependency)
├── repositories/           persistence (SQLAlchemy/SQLModel)
├── models/                 ORM models (if SQLAlchemy)
└── lib/                    cross-cutting utilities
```

## Pydantic v2 — the contract layer

Pydantic v2 (rewrite in Rust; ~17x faster than v1) is the validation + serialization layer:

```python
# schemas/order.py
from pydantic import BaseModel, Field, UUID4
from typing import Annotated

class LineItem(BaseModel):
    sku: Annotated[str, Field(min_length=1)]
    quantity: Annotated[int, Field(gt=0)]

class CreateOrderRequest(BaseModel):
    customer_id: UUID4
    items: Annotated[list[LineItem], Field(min_length=1)]

class OrderResponse(BaseModel):
    order_id: UUID4
    status: Literal['pending', 'confirmed']
```

Then in a router:

```python
# routers/orders.py
from fastapi import APIRouter, Depends, HTTPException, status
from ..schemas.order import CreateOrderRequest, OrderResponse
from ..services.order_service import OrderService
from ..deps import get_order_service

router = APIRouter(prefix='/orders', tags=['orders'])

@router.post('', response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: CreateOrderRequest,
    svc: OrderService = Depends(get_order_service),
) -> OrderResponse:
    order = await svc.create(body)
    return OrderResponse(order_id=order.id, status=order.status)
```

The `response_model` enforces the response shape AND filters extra fields out — useful for not leaking ORM fields.

## Dependency injection — `Depends`

FastAPI's `Depends()` is the right pattern for everything cross-cutting: DB sessions, auth, settings, services.

```python
# deps.py
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from .db import async_session_factory
from .services.order_service import OrderService

async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

async def current_user_id(authorization: str = Header(...)) -> UUID:
    token = authorization.removeprefix('Bearer ').strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    return await verify_token(token)

def get_order_service(
    session: AsyncSession = Depends(db_session),
) -> OrderService:
    return OrderService(session)
```

Dependencies compose: `Depends(get_order_service)` triggers `Depends(db_session)` automatically.

## Async I/O — the default

FastAPI assumes async. For DB use SQLAlchemy 2.x async or SQLModel:

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
```

If a dependency must be sync (a legacy library), wrap with `run_in_threadpool` — but track the threadpool exhaustion if it's hot.

## Error handling

Use `HTTPException` for client errors; let unhandled exceptions surface to the global handler:

```python
# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

app = FastAPI(title='Order Service', version='1.0.0')
log = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    log.exception('unhandled exception', extra={'request_id': request.headers.get('x-request-id')})
    return JSONResponse(status_code=500, content={'error': 'internal_error'})

# Pydantic validation errors → 422 by default; customize if needed:
from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={'error': 'validation_error', 'details': exc.errors()},
    )
```

## Observability

```python
# main.py
import logging
import structlog
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Configure structlog for JSON logs
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.JSONRenderer(),
    ],
)

# Instrument FastAPI for OpenTelemetry — traces propagate per `observability`
FastAPIInstrumentor.instrument_app(app)

@app.middleware('http')
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get('x-request-id') or str(uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers['x-request-id'] = request_id
    return response
```

## Settings — `pydantic-settings`

```python
# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, SecretStr

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')
    database_url: PostgresDsn
    secret_key: SecretStr
    log_level: str = 'INFO'

settings = Settings()   # loads from env at import
```

Per `secrets-config`, prod secrets come from a real secret store; `.env` is dev-only.

## Testing

`pytest` + `httpx.AsyncClient`:

```python
# tests/test_orders.py
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.mark.asyncio
async def test_create_order_returns_201(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        r = await client.post(
            '/orders',
            headers={'authorization': 'Bearer test-token'},
            json={'customer_id': '...', 'items': [{'sku': 'X', 'quantity': 1}]},
        )
        assert r.status_code == 201
        assert 'order_id' in r.json()
```

For integration tests, Testcontainers per `testing-strategy` (`testcontainers-python` package).

## Auto-generated OpenAPI

FastAPI generates OpenAPI 3.x from your code + Pydantic models. Visit `/docs` (Swagger UI) or `/redoc`. Per `api-design`, this becomes the contract; consumers generate clients from it.

To customize:

```python
app = FastAPI(
    title='Order Service',
    version='1.0.0',
    summary='Order management API',
    description='...',
    contact={'name': 'Platform Team', 'email': 'platform@example.com'},
    license_info={'name': 'Proprietary'},
    servers=[{'url': 'https://api.example.com'}],
)
```

## Performance baseline

FastAPI runs on Starlette + uvicorn. Typical sync workload: ~10-15K rps; async I/O bound: ~25K+ rps (depends on what the I/O is). For absolute max throughput consider hypercorn instead of uvicorn, but the delta is small.

## Gotchas

- **`async def` for IO; `def` for CPU** — sync handlers run in a thread pool; pure-CPU work blocks the event loop if not.
- **Pydantic v2 vs v1 syntax** — major breaking changes; ensure deps are v2-compatible (some popular libs took time to migrate).
- **Background tasks via `BackgroundTasks`** — fine for in-request fire-and-forget; NOT a job queue. Use Celery / RQ / Dramatiq / arq for real background work.
- **`response_model` with `orm_mode`** — Pydantic v2 calls this `from_attributes=True`; configure via `model_config`.
- **Mutable default arguments in Pydantic models** — same Python footgun; use `Field(default_factory=list)`.

## Official sources

- FastAPI: https://fastapi.tiangolo.com
- Pydantic v2: https://docs.pydantic.dev/latest/
- SQLAlchemy 2.x async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- structlog: https://www.structlog.org
- uvicorn: https://www.uvicorn.org

## Common rationalizations

| Thought | Counter |
|---|---|
| "Skip Pydantic; just use dicts." | Pydantic gives validation + serialization + OpenAPI for free. Worth its weight. |
| "Make everything async." | Pure-CPU async = blocking event loop. Async only when there's actual I/O concurrency. |
| "Use BackgroundTasks for the worker queue." | BackgroundTasks runs in-process; if the request was the trigger, the work dies if the request times out. Use a real queue. |
| "Generate clients from /docs once; we're done." | Regenerate clients on every release; the spec is the contract, and it can change. |
