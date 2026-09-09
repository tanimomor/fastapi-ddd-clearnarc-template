from application.events.interface import EventHandler
from domain.author.events import AuthorDeleted
from domain.book.repository import BookRepository


class DeleteBooksOfDeletedAuthorHandler(EventHandler[AuthorDeleted]):
    """Removes the books of an author that no longer exists.

    Note the direction of the dependency: the *book* module imports the *author*
    module's event contract. The author module knows nothing about books, so
    deleting an author never drags book behaviour into its service.

    Caveat, deliberately not hidden: this runs on the in-memory bus, after the
    author deletion has already been applied. If the process dies in between, or
    if this handler raises, the author is gone while the books remain. That is
    acceptable for an in-process bus; making the two changes atomic requires
    either one transaction spanning both modules (which reintroduces the
    coupling) or a transactional outbox.
    """

    def __init__(self, repository: BookRepository):
        self._repository = repository

    async def handle(self, event: AuthorDeleted) -> None:
        for book in self._repository.list_by_author(event.aggregate_id):
            self._repository.delete(book.id)
