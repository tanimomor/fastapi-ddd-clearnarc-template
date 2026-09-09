from uuid import UUID, uuid4

from application.author.interface import IAuthorAppService
from contracts.author.author_schema import AuthorSchema
from contracts.author.create_author_schema import CreateAuthorSchema
from contracts.author.get_author_list_schema import GetAuthorListSchema
from contracts.author.update_author_schema import UpdateAuthorSchema
from domain.author.entities import Author
from domain.author.exceptions import AuthorNotFoundError
from domain.author.repository import AuthorRepository


class AuthorService(IAuthorAppService):
    def __init__(self, repository: AuthorRepository):
        self._repository = repository

    def create(self, schema: CreateAuthorSchema) -> AuthorSchema:
        author = Author(
            id=uuid4(),
            first_name=schema.first_name,
            last_name=schema.last_name,
            bio=schema.bio,
        )
        self._repository.add(author)
        return AuthorSchema.model_validate(author)

    def get(self, author_id: UUID) -> AuthorSchema:
        return AuthorSchema.model_validate(self._get_entity(author_id))

    def get_list(self) -> GetAuthorListSchema:
        authors = self._repository.list()
        return GetAuthorListSchema(
            items=[AuthorSchema.model_validate(author) for author in authors],
            total_count=len(authors),
        )

    def update(self, author_id: UUID, schema: UpdateAuthorSchema) -> AuthorSchema:
        author = self._get_entity(author_id)
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(author, field, value)
        self._repository.add(author)
        return AuthorSchema.model_validate(author)

    def delete(self, author_id: UUID) -> None:
        self._get_entity(author_id)
        self._repository.delete(author_id)

    def _get_entity(self, author_id: UUID) -> Author:
        author = self._repository.get(author_id)
        if author is None:
            raise AuthorNotFoundError(author_id)
        return author
