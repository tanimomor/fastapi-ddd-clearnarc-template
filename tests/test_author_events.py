"""End-to-end checks that the wiring actually delivers cross-domain behaviour."""

import ast
import pathlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_author_repository, get_book_repository
from application.author.service import AuthorService
from application.book.event_handlers import DeleteBooksOfDeletedAuthorHandler
from application.events.interface import IEventPublisher
from contracts.author.create_author_schema import CreateAuthorSchema
from domain.author.events import AuthorDeleted
from domain.author.exceptions import AuthorNotFoundError
from domain.book.entities import Book
from infrastructure.persistence.in_memory_author_repository import InMemoryAuthorRepository
from infrastructure.persistence.in_memory_book_repository import InMemoryBookRepository
from main import app
from shared_domain.events.event import Event


class RecordingPublisher(IEventPublisher):
    """A publisher test double: services should not need a real bus to be tested."""

    def __init__(self) -> None:
        self.published: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.published.append(event)

    async def publish_many(self, events) -> None:
        self.published.extend(events)


@pytest.fixture(autouse=True)
def reset_shared_repositories():
    """The application's repositories are process-wide singletons; keep tests isolated."""
    get_author_repository.cache_clear()
    get_book_repository.cache_clear()
    yield
    get_author_repository.cache_clear()
    get_book_repository.cache_clear()


# --- the publishing side --------------------------------------------------


async def test_deleting_an_author_publishes_author_deleted():
    repository = InMemoryAuthorRepository()
    publisher = RecordingPublisher()
    service = AuthorService(repository, publisher)
    author = await service.create(CreateAuthorSchema(first_name="Ada", last_name="Lovelace"))

    await service.delete(author.id)

    assert len(publisher.published) == 1
    event = publisher.published[0]
    assert isinstance(event, AuthorDeleted)
    assert event.aggregate_id == author.id


async def test_the_event_is_published_only_after_the_author_is_removed():
    repository = InMemoryAuthorRepository()
    observed: list[bool] = []

    class AssertingPublisher(RecordingPublisher):
        async def publish(self, event: Event) -> None:
            observed.append(repository.get(event.aggregate_id) is None)
            await super().publish(event)

    service = AuthorService(repository, AssertingPublisher())
    author = await service.create(CreateAuthorSchema(first_name="Ada", last_name="Lovelace"))

    await service.delete(author.id)

    assert observed == [True], "subscribers must never observe a not-yet-applied change"


async def test_nothing_is_published_when_the_author_does_not_exist():
    publisher = RecordingPublisher()
    service = AuthorService(InMemoryAuthorRepository(), publisher)

    with pytest.raises(AuthorNotFoundError):
        await service.delete(uuid4())

    assert publisher.published == []


# --- the consuming side ---------------------------------------------------


async def test_the_handler_removes_only_the_deleted_authors_books():
    repository = InMemoryBookRepository()
    deleted_author_id, other_author_id = uuid4(), uuid4()
    repository.add(Book(id=uuid4(), title="Notes", author_id=deleted_author_id))
    kept = Book(id=uuid4(), title="Other", author_id=other_author_id)
    repository.add(kept)

    await DeleteBooksOfDeletedAuthorHandler(repository).handle(
        AuthorDeleted(aggregate_id=deleted_author_id)
    )

    assert repository.list() == [kept]


# --- the whole path through the running application -----------------------


def test_deleting_an_author_through_the_api_removes_their_books():
    with TestClient(app) as client:
        author_id = client.post(
            "/authors", json={"first_name": "Ada", "last_name": "Lovelace"}
        ).json()["id"]
        client.post("/books", json={"title": "Notes", "author_id": author_id})
        assert client.get("/books").json()["total_count"] == 1

        assert client.delete(f"/authors/{author_id}").status_code == 204

        assert client.get("/books").json()["total_count"] == 0


def test_the_application_closes_the_bus_on_shutdown():
    with TestClient(app) as client:
        client.get("/health")
        bus = app.state.event_bus
        assert bus.is_closed is False

    assert bus.is_closed is True


def test_each_application_run_gets_its_own_bus():
    with TestClient(app):
        first = app.state.event_bus
    with TestClient(app):
        second = app.state.event_bus

    assert first is not second


# --- the dependency rule --------------------------------------------------


def _imported_modules(path: str) -> set[str]:
    tree = ast.parse(pathlib.Path(path).read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


@pytest.mark.parametrize(
    "path",
    [
        "application/author/service.py",
        "application/author/interface.py",
        "domain/author/events.py",
        "api/routes/authors.py",
    ],
)
def test_the_publishing_module_never_imports_the_consuming_module(path):
    """The point of the bus: deleting an author triggers book behaviour that the
    author module has no reference to."""
    assert not any(
        module.startswith(("application.book", "domain.book", "contracts.book"))
        for module in _imported_modules(path)
    )


def test_the_consumer_depends_only_on_the_published_contract():
    imports = _imported_modules("application/book/event_handlers.py")

    assert "domain.author.events" in imports
    assert not any(module.startswith("application.author") for module in imports)


def test_application_services_receive_only_the_publish_only_interface():
    imports = _imported_modules("application/author/service.py")

    assert "application.events.interface" in imports
    assert not any(module.startswith("infrastructure.events") for module in imports)
