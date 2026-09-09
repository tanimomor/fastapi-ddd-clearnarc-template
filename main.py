from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.events import register_event_handlers
from api.exceptions import register_exception_handlers
from api.routes.authors import router as authors_router
from api.routes.books import router as books_router
from infrastructure.events.in_memory_event_bus import InMemoryEventBus


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    event_bus = InMemoryEventBus()
    register_event_handlers(event_bus)
    app.state.event_bus = event_bus
    try:
        yield
    finally:
        await event_bus.aclose()


app = FastAPI(title="FastAPI DDD Clean Architecture", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(authors_router)
app.include_router(books_router)


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
