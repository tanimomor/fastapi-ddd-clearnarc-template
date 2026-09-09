from pydantic import BaseModel

from contracts.book.book_schema import BookSchema


class GetBookListSchema(BaseModel):
    items: list[BookSchema]
    total_count: int
