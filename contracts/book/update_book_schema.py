from pydantic import BaseModel

from shared_domain.book_type import BookType


class UpdateBookSchema(BaseModel):
    title: str | None = None
    book_type: BookType | None = None
    isbn: str | None = None
    published_year: int | None = None
