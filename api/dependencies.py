from functools import lru_cache

from application.author.interface import IAuthorAppService
from application.author.service import AuthorService
from application.book.interface import IBookAppService
from application.book.service import BookService
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


def get_author_service() -> IAuthorAppService:
    return AuthorService(get_author_repository())


def get_book_service() -> IBookAppService:
    return BookService(get_book_repository(), get_author_repository())
