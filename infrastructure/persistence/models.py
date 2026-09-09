import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.persistence.db import Base
from shared_domain.book_type import BookType


class AuthorModel(Base):
    __tablename__ = "authors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str]
    last_name: Mapped[str]
    bio: Mapped[str | None] = mapped_column(default=None)

    books: Mapped[list["BookModel"]] = relationship(back_populates="author")


class BookModel(Base):
    __tablename__ = "books"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str]
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authors.id"))
    book_type: Mapped[BookType] = mapped_column(default=BookType.OTHER)
    isbn: Mapped[str | None] = mapped_column(default=None)
    published_year: Mapped[int | None] = mapped_column(default=None)

    author: Mapped["AuthorModel"] = relationship(back_populates="books")
