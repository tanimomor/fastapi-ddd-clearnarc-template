from pydantic import BaseModel


class UpdateAuthorSchema(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    bio: str | None = None
