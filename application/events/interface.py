from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence

from shared_domain.events.event import Event


type EventHandlerCallable[EventT: Event] = Callable[[EventT], Awaitable[None]]
"""Anything that can consume an event: a coroutine function, a bound method, or
an :class:`EventHandler` instance."""


class EventHandler[EventT: Event](ABC):
    """Recommended base class for handlers that need collaborators injected.

    Handlers are application-layer objects: they react to an event by driving a
    use case. A handler receives the event and nothing else - in particular it
    does not receive the bus, so it cannot be used to smuggle a service locator
    into a module. A handler that legitimately needs to publish a follow-up event
    takes an :class:`IEventPublisher` through its constructor like any other
    dependency.
    """

    @abstractmethod
    async def handle(self, event: EventT) -> None: ...

    async def __call__(self, event: EventT) -> None:
        await self.handle(event)


class IEventPublisher(ABC):
    """The only event-bus surface an application service should depend on.

    Publishers know event contracts, not consumers: this interface exposes no way
    to enumerate, register or inspect handlers, so a publishing module cannot
    grow a dependency on a subscribing one.
    """

    @abstractmethod
    async def publish(self, event: Event) -> None:
        """Dispatch one event to every subscribed handler.

        Handlers run in registration order, one after another, and are awaited
        before this returns. If any handler fails, the remaining handlers still
        run and an :class:`~application.events.exceptions.EventDispatchError`
        aggregating the failures is raised afterwards.
        """

    @abstractmethod
    async def publish_many(self, events: Sequence[Event]) -> None:
        """Dispatch events in the given order, each one fully before the next.

        This is a convenience over repeated :meth:`publish`, not a transaction:
        a failure in one event's handlers does not prevent later events from
        being dispatched, and nothing is rolled back.
        """


class IEventBus(IEventPublisher):
    """The full bus, owned by the composition root.

    Registration and lifecycle live here rather than on
    :class:`IEventPublisher` so that only the wiring layer can reach them.
    """

    @abstractmethod
    def subscribe[EventT: Event](
        self, event_type: type[EventT], handler: EventHandlerCallable[EventT]
    ) -> None:
        """Register ``handler`` for ``event_type`` and all of its subclasses."""

    @abstractmethod
    def unsubscribe[EventT: Event](
        self, event_type: type[EventT], handler: EventHandlerCallable[EventT]
    ) -> None:
        """Remove a previously registered subscription."""

    @abstractmethod
    async def aclose(self) -> None:
        """Stop accepting publishes, wait for in-flight dispatches, drop handlers."""
