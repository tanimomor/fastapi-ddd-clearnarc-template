from uuid import UUID

from fastapi import APIRouter, Depends, status

from application.book.interface import IBookAppService
from contracts.book.book_schema import BookSchema
from contracts.book.create_book_schema import CreateBookSchema
from contracts.book.get_book_list_schema import GetBookListSchema
from contracts.book.update_book_schema import UpdateBookSchema
from api.dependencies import get_book_service

router = APIRouter(prefix="/books", tags=["Books"])


@router.post("", response_model=BookSchema, status_code=status.HTTP_201_CREATED)
def create_book(
    body: CreateBookSchema,
    service: IBookAppService = Depends(get_book_service),
) -> BookSchema:
    return service.create(body)


@router.get("", response_model=GetBookListSchema)
def list_books(
    author_id: UUID | None = None,
    service: IBookAppService = Depends(get_book_service),
) -> GetBookListSchema:
    if author_id is not None:
        return service.get_list_by_author(author_id)
    return service.get_list()


@router.get("/{book_id}", response_model=BookSchema)
def get_book(
    book_id: UUID,
    service: IBookAppService = Depends(get_book_service),
) -> BookSchema:
    return service.get(book_id)


@router.put("/{book_id}", response_model=BookSchema)
def update_book(
    book_id: UUID,
    body: UpdateBookSchema,
    service: IBookAppService = Depends(get_book_service),
) -> BookSchema:
    return service.update(book_id, body)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: UUID,
    service: IBookAppService = Depends(get_book_service),
) -> None:
    service.delete(book_id)
