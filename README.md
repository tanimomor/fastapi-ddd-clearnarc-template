# FastAPI DDD Clean Architecture

A FastAPI backend organized around Domain-Driven Design and Clean Architecture,
with a companion Next.js frontend. Books and Authors are the sample bounded
contexts wired through every layer, including an in-process domain event bus.

## Architecture

The codebase is layered so dependencies only point inward — `api` depends on
`application`, `application` depends on `domain`, and `domain` depends on
nothing else in the project.

```
domain/            Entities, repository interfaces, domain events, exceptions.
                    No framework, no I/O, no dependency on any other layer.
application/        Use-case services and their interfaces. Orchestrates domain
                    objects and repositories; depends only on domain + contracts.
contracts/          Pydantic request/response schemas (the API's DTOs),
                    per-resource: <name>_schema.py, create_<name>_schema.py,
                    update_<name>_schema.py, get_<name>_list_schema.py.
infrastructure/     Concrete implementations of domain interfaces: persistence
                    (in-memory repos + SQLAlchemy models/engine) and the event
                    bus. This is the only layer allowed to know about
                    SQLAlchemy, asyncio internals, etc.
api/                FastAPI routers, dependency wiring, and exception→HTTP
                    translation. Owns the HTTP concern only.
shared_domain/      Value types and the base Event model shared across bounded
                    contexts (e.g. BookType, the Event/DomainEvent hierarchy).
db_migrator/        Alembic migration environment and versions.
web/                Next.js frontend that consumes the API.
tests/              Pytest suite (currently covers the event bus).
```

Each bounded context (`author`, `book`) repeats the same shape across
`domain/`, `application/` and `contracts/`:

```
domain/author/
  entities.py       Author dataclass
  repository.py     AuthorRepository (ABC) — the port
  events.py         AuthorDeleted, ...
  exceptions.py     AuthorNotFoundError

application/author/
  interface.py       IAuthorAppService (ABC)
  service.py          AuthorService(IAuthorAppService) — the use cases

contracts/author/
  author_schema.py            AuthorSchema (response)
  create_author_schema.py     CreateAuthorSchema
  update_author_schema.py     UpdateAuthorSchema
  get_author_list_schema.py   GetAuthorListSchema
```

Application services depend on repository **interfaces**, not concrete
classes — `api/dependencies.py` is the composition root that decides which
concrete repository (currently in-memory) and event publisher get injected.

## Domain events

An in-process event bus (`infrastructure/events/in_memory_event_bus.py`) lets
one bounded context react to another without a direct dependency. Example:
deleting an author publishes `AuthorDeleted`; `application/book/event_handlers.py`
subscribes to it and deletes that author's books — the `book` module imports
the `author` module's event, never the reverse.

- **Event hierarchy** (`shared_domain/events/event.py`): `DomainEvent` (an
  in-process fact about one aggregate), `ApplicationEvent` (infra-flavoured
  signal), `IntegrationEvent` (a versioned cross-process contract — the
  in-memory bus refuses to publish these on purpose, since it offers no
  durability or retries).
- **Publishing**: application services take an `IEventPublisher` (publish-only)
  through their constructor; only the composition root sees the full
  `IEventBus` (subscribe/unsubscribe).
- **Wiring**: every subscription is registered in one place —
  `api/events.py` — mirroring how `api/exceptions.py` centralizes error
  mapping.
- **Guarantees**: handlers run sequentially, in registration order, awaited in
  the publisher's own task. In-order, at-most-once, best-effort, in-process
  delivery — no durability, no cross-process delivery. See the module
  docstrings in `infrastructure/events/in_memory_event_bus.py` and
  `api/events.py` for when a transactional outbox becomes necessary instead.

## Prerequisites

- Python 3.12+ (the codebase uses PEP 695 generic syntax)
- Node.js 20+ (for `web/`)
- Docker (optional, for a local Postgres instance)

## Backend setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Run

```bash
uvicorn main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs (Swagger UI): http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json

> If port 8000 is already taken on your machine, run with `--port <other>`
> and update `web/.env.local`'s `NEXT_PUBLIC_API_URL` to match.

### Test

```bash
pip install -r requirements-dev.txt
pytest
```

## Database (Postgres)

SQLAlchemy models, an async engine, and Alembic migrations are already set up
under `infrastructure/persistence/` and `db_migrator/`, but the application
services currently run against **in-memory repositories**
(`infrastructure/persistence/in_memory_*_repository.py`), wired in
`api/dependencies.py`. The ORM models exist and migrations are ready to run,
but nothing persists to Postgres yet — swapping `api/dependencies.py` to
construct SQLAlchemy-backed repositories instead is the remaining step.

Start Postgres locally:

```bash
docker compose up -d
```

Run migrations:

```bash
alembic upgrade head
```

Create a new migration after changing `infrastructure/persistence/models.py`:

```bash
alembic revision --autogenerate -m "describe the change"
```

Connection settings live in `infrastructure/config.py` (`Settings`), sourced
from `.env` — see `.env.example` for the full list (`POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`).

## API overview

| Method | Path                       | Description                          |
|--------|----------------------------|---------------------------------------|
| POST   | `/authors`                 | Create an author                     |
| GET    | `/authors`                 | List authors                         |
| GET    | `/authors/{author_id}`     | Get one author                       |
| PUT    | `/authors/{author_id}`     | Update an author                     |
| DELETE | `/authors/{author_id}`     | Delete an author (publishes `AuthorDeleted`) |
| POST   | `/books`                   | Create a book                        |
| GET    | `/books`                   | List books (`?author_id=` to filter) |
| GET    | `/books/{book_id}`         | Get one book                         |
| PUT    | `/books/{book_id}`         | Update a book                        |
| DELETE | `/books/{book_id}`         | Delete a book                        |

A `*NotFoundError` raised by a service is translated to a `404` with a JSON
`{"detail": "..."}` body by `api/exceptions.py`.

## Frontend (`web/`)

A Next.js (App Router, TypeScript, Tailwind) app that calls the API directly.

```bash
cd web
npm install
npm run dev
```

- `web/.env.local` — `NEXT_PUBLIC_API_URL` (defaults to the local backend)
- `web/lib/types.ts` — TypeScript types mirroring the `contracts/` Pydantic schemas
- `web/lib/api.ts` — typed `fetch` client (`api.authors.*`, `api.books.*`)

The backend must be running (see above) and `CORSMiddleware` in `main.py`
allows `http://localhost:3000` by default.

## Adding a new bounded context

1. `domain/<name>/` — entity, repository interface, exceptions, events.
2. `application/<name>/` — `I<Name>AppService` interface + implementation.
3. `contracts/<name>/` — `<name>_schema.py`, `create_<name>_schema.py`,
   `update_<name>_schema.py`, `get_<name>_list_schema.py`.
4. `infrastructure/persistence/` — repository implementation (in-memory and/or
   SQLAlchemy).
5. `api/dependencies.py` — wire the interface to its implementation.
6. `api/routes/<name>.py` — `APIRouter` calling the service; include it in `main.py`.
7. If it raises a new not-found-style exception, register it in
   `api/exceptions.py`.
8. If it publishes or reacts to events, add the subscription in `api/events.py`.
