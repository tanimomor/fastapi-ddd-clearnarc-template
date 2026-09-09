from uuid import UUID

from pydantic import BaseModel

from shared_domain.book_type import BookType


class CreateBookSchema(BaseModel):
    title: str
    author_id: UUID
    book_type: BookType = BookType.OTHER
    isbn: str | None = None
    published_year: int | None = None
