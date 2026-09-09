from uuid import UUID

from fastapi import APIRouter, Depends, status

from application.author.interface import IAuthorAppService
from contracts.author.author_schema import AuthorSchema
from contracts.author.create_author_schema import CreateAuthorSchema
from contracts.author.get_author_list_schema import GetAuthorListSchema
from contracts.author.update_author_schema import UpdateAuthorSchema
from api.dependencies import get_author_service

router = APIRouter(prefix="/authors", tags=["Authors"])


@router.post("", response_model=AuthorSchema, status_code=status.HTTP_201_CREATED)
def create_author(
    body: CreateAuthorSchema,
    service: IAuthorAppService = Depends(get_author_service),
) -> AuthorSchema:
    return service.create(body)


@router.get("", response_model=GetAuthorListSchema)
def list_authors(
    service: IAuthorAppService = Depends(get_author_service),
) -> GetAuthorListSchema:
    return service.get_list()


@router.get("/{author_id}", response_model=AuthorSchema)
def get_author(
    author_id: UUID,
    service: IAuthorAppService = Depends(get_author_service),
) -> AuthorSchema:
    return service.get(author_id)


@router.put("/{author_id}", response_model=AuthorSchema)
def update_author(
    author_id: UUID,
    body: UpdateAuthorSchema,
    service: IAuthorAppService = Depends(get_author_service),
) -> AuthorSchema:
    return service.update(author_id, body)


@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(
    author_id: UUID,
    service: IAuthorAppService = Depends(get_author_service),
) -> None:
    service.delete(author_id)
