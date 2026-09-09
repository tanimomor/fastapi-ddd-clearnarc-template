from pydantic import BaseModel

from contracts.author.author_schema import AuthorSchema


class GetAuthorListSchema(BaseModel):
    items: list[AuthorSchema]
    total_count: int
