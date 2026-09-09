from abc import ABC, abstractmethod
from uuid import UUID

from domain.book.entities import Book


class BookRepository(ABC):
    @abstractmethod
    def add(self, book: Book) -> None: ...

    @abstractmethod
    def get(self, book_id: UUID) -> Book | None: ...

    @abstractmethod
    def list(self) -> list[Book]: ...

    @abstractmethod
    def list_by_author(self, author_id: UUID) -> list[Book]: ...

    @abstractmethod
    def delete(self, book_id: UUID) -> None: ...
