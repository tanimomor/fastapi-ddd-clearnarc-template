from functools import lru_cache

from fastapi import Depends, Request

from application.author.interface import IAuthorAppService
from application.author.service import AuthorService
from application.book.interface import IBookAppService
from application.book.service import BookService
from application.events.interface import IEventBus, IEventPublisher
from domain.author.repository import AuthorRepository
from domain.book.repository import BookRepository
from infrastructure.persistence.in_memory_author_repository import InMemoryAuthorRepository
from infrastructure.persistence.in_memory_book_repository import InMemoryBookRepository


@lru_cache
def get_author_repository() -> AuthorRepository:
    return InMemoryAuthorRepository()


@lru_cache
def get_book_repository() -> BookRepository:
    return InMemoryBookRepository()


def get_event_bus(request: Request) -> IEventBus:
    """The bus owned by this application instance.

    Held on ``app.state`` rather than in a module-level singleton so its
    lifetime is exactly the application's lifetime: two apps in the same process
    (as in tests) get two independent buses, and nothing survives shutdown.
    """
    return request.app.state.event_bus


def get_event_publisher(bus: IEventBus = Depends(get_event_bus)) -> IEventPublisher:
    """Application services get the publish-only view: they cannot subscribe."""
    return bus


def get_author_service(
    event_publisher: IEventPublisher = Depends(get_event_publisher),
) -> IAuthorAppService:
    return AuthorService(get_author_repository(), event_publisher)


def get_book_service() -> IBookAppService:
    return BookService(get_book_repository(), get_author_repository())
