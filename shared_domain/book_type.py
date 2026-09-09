from enum import Enum


class BookType(str, Enum):
    FICTION = "fiction"
    NON_FICTION = "non_fiction"
    BIOGRAPHY = "biography"
    SCIENCE = "science"
    HISTORY = "history"
    POETRY = "poetry"
    OTHER = "other"
