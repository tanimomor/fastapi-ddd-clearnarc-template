from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from domain.author.exceptions import AuthorNotFoundError
from domain.book.exceptions import BookNotFoundError


def _not_found_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthorNotFoundError, _not_found_handler)
    app.add_exception_handler(BookNotFoundError, _not_found_handler)
