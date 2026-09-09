from abc import ABC, abstractmethod
from uuid import UUID

from contracts.author.author_schema import AuthorSchema
from contracts.author.create_author_schema import CreateAuthorSchema
from contracts.author.get_author_list_schema import GetAuthorListSchema
from contracts.author.update_author_schema import UpdateAuthorSchema


class IAuthorAppService(ABC):
    @abstractmethod
    async def create(self, schema: CreateAuthorSchema) -> AuthorSchema: ...

    @abstractmethod
    async def get(self, author_id: UUID) -> AuthorSchema: ...

    @abstractmethod
    async def get_list(self) -> GetAuthorListSchema: ...

    @abstractmethod
    async def update(self, author_id: UUID, schema: UpdateAuthorSchema) -> AuthorSchema: ...

    @abstractmethod
    async def delete(self, author_id: UUID) -> None: ...
