from dataclasses import dataclass
from uuid import UUID

from shared_domain.book_type import BookType


@dataclass
class Book:
    id: UUID
    title: str
    author_id: UUID
    book_type: BookType = BookType.OTHER
    isbn: str | None = None
    published_year: int | None = None
