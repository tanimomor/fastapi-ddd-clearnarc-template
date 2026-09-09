from abc import ABC, abstractmethod
from uuid import UUID

from domain.author.entities import Author


class AuthorRepository(ABC):
    @abstractmethod
    def add(self, author: Author) -> None: ...

    @abstractmethod
    def get(self, author_id: UUID) -> Author | None: ...

    @abstractmethod
    def list(self) -> list[Author]: ...

    @abstractmethod
    def delete(self, author_id: UUID) -> None: ...
