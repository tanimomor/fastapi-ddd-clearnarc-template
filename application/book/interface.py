from abc import ABC, abstractmethod
from uuid import UUID

from contracts.book.book_schema import BookSchema
from contracts.book.create_book_schema import CreateBookSchema
from contracts.book.get_book_list_schema import GetBookListSchema
from contracts.book.update_book_schema import UpdateBookSchema


class IBookAppService(ABC):
    @abstractmethod
    def create(self, schema: CreateBookSchema) -> BookSchema: ...

    @abstractmethod
    def get(self, book_id: UUID) -> BookSchema: ...

    @abstractmethod
    def get_list(self) -> GetBookListSchema: ...

    @abstractmethod
    def get_list_by_author(self, author_id: UUID) -> GetBookListSchema: ...

    @abstractmethod
    def update(self, book_id: UUID, schema: UpdateBookSchema) -> BookSchema: ...

    @abstractmethod
    def delete(self, book_id: UUID) -> None: ...
