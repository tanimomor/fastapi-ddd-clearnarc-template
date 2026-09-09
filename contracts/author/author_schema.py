from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuthorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    bio: str | None = None
