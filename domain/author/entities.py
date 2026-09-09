from dataclasses import dataclass
from uuid import UUID


@dataclass
class Author:
    id: UUID
    first_name: str
    last_name: str
    bio: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
