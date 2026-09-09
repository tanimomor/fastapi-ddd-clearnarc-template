"""Event-handler composition root.

Every subscription in the application is declared here, mirroring
``api/exceptions.py``. Centralising registration is what keeps the dependency
rule enforceable: a module publishes an event without importing, or even
knowing about, whatever reacts to it - the wiring layer is the only place where
both sides meet.

Where the in-memory bus stops
-----------------------------
Handlers run after the originating operation has been applied, in the same task,
with no durability. That is the right trade-off while every consumer lives in
this process and the work is recoverable. Introduce a transactional outbox -
writing events to the same database transaction as the state change, with a
relay publishing them afterwards - as soon as one of these becomes true:

* a handler must survive a process crash between commit and dispatch;
* a consumer moves out of process (that is what ``IntegrationEvent`` marks, and
  why the in-memory bus refuses to publish one);
* at-least-once delivery is required rather than best effort.

At that point the outbox sits behind its own publisher interface and this bus
keeps serving the in-process subscribers unchanged.

Handler lifetime
----------------
Handlers are constructed once, at startup, and live as long as the application.
That is correct while repositories are process-wide singletons. Once they are
backed by a real ``AsyncSession``, a handler must not capture one: sessions are
request-scoped. Inject a session *factory* instead and open a session inside
``handle`` - the handler then owns its own unit of work, which is also what
makes it independent of whether the publisher's transaction committed.
"""

from api.dependencies import get_book_repository
from application.book.event_handlers import DeleteBooksOfDeletedAuthorHandler
from application.events.interface import IEventBus
from domain.author.events import AuthorDeleted


def register_event_handlers(bus: IEventBus) -> None:
    bus.subscribe(AuthorDeleted, DeleteBooksOfDeletedAuthorHandler(get_book_repository()))
