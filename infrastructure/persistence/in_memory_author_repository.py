from uuid import UUID

from domain.author.entities import Author
from domain.author.repository import AuthorRepository


class InMemoryAuthorRepository(AuthorRepository):
    def __init__(self):
        self._authors: dict[UUID, Author] = {}

    def add(self, author: Author) -> None:
        self._authors[author.id] = author

    def get(self, author_id: UUID) -> Author | None:
        return self._authors.get(author_id)

    def list(self) -> list[Author]:
        return list(self._authors.values())

    def delete(self, author_id: UUID) -> None:
        self._authors.pop(author_id, None)
