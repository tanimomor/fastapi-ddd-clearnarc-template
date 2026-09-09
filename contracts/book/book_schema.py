from uuid import UUID

from pydantic import BaseModel, ConfigDict

from shared_domain.book_type import BookType


class BookSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    author_id: UUID
    book_type: BookType
    isbn: str | None = None
    published_year: int | None = None
