from uuid import UUID, uuid4

from application.book.interface import IBookAppService
from contracts.book.book_schema import BookSchema
from contracts.book.create_book_schema import CreateBookSchema
from contracts.book.get_book_list_schema import GetBookListSchema
from contracts.book.update_book_schema import UpdateBookSchema
from domain.author.exceptions import AuthorNotFoundError
from domain.author.repository import AuthorRepository
from domain.book.entities import Book
from domain.book.exceptions import BookNotFoundError
from domain.book.repository import BookRepository


class BookService(IBookAppService):
    def __init__(self, repository: BookRepository, author_repository: AuthorRepository):
        self._repository = repository
        self._author_repository = author_repository

    def create(self, schema: CreateBookSchema) -> BookSchema:
        if self._author_repository.get(schema.author_id) is None:
            raise AuthorNotFoundError(schema.author_id)

        book = Book(
            id=uuid4(),
            title=schema.title,
            author_id=schema.author_id,
            book_type=schema.book_type,
            isbn=schema.isbn,
            published_year=schema.published_year,
        )
        self._repository.add(book)
        return BookSchema.model_validate(book)

    def get(self, book_id: UUID) -> BookSchema:
        return BookSchema.model_validate(self._get_entity(book_id))

    def get_list(self) -> GetBookListSchema:
        books = self._repository.list()
        return GetBookListSchema(
            items=[BookSchema.model_validate(book) for book in books],
            total_count=len(books),
        )

    def get_list_by_author(self, author_id: UUID) -> GetBookListSchema:
        books = self._repository.list_by_author(author_id)
        return GetBookListSchema(
            items=[BookSchema.model_validate(book) for book in books],
            total_count=len(books),
        )

    def update(self, book_id: UUID, schema: UpdateBookSchema) -> BookSchema:
        book = self._get_entity(book_id)
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(book, field, value)
        self._repository.add(book)
        return BookSchema.model_validate(book)

    def delete(self, book_id: UUID) -> None:
        self._get_entity(book_id)
        self._repository.delete(book_id)

    def _get_entity(self, book_id: UUID) -> Book:
        book = self._repository.get(book_id)
        if book is None:
            raise BookNotFoundError(book_id)
        return book
