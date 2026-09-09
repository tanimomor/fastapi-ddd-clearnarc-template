from pydantic import BaseModel


class CreateAuthorSchema(BaseModel):
    first_name: str
    last_name: str
    bio: str | None = None
