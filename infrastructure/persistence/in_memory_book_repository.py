from uuid import UUID

from domain.book.entities import Book
from domain.book.repository import BookRepository


class InMemoryBookRepository(BookRepository):
    def __init__(self):
        self._books: dict[UUID, Book] = {}

    def add(self, book: Book) -> None:
        self._books[book.id] = book

    def get(self, book_id: UUID) -> Book | None:
        return self._books.get(book_id)

    def list(self) -> list[Book]:
        return list(self._books.values())

    def list_by_author(self, author_id: UUID) -> list[Book]:
        return [book for book in self._books.values() if book.author_id == author_id]

    def delete(self, book_id: UUID) -> None:
        self._books.pop(book_id, None)
