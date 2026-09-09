from collections.abc import Callable

from application.events.exceptions import DuplicateHandlerError, HandlerNotRegisteredError
from application.events.interface import EventHandler, EventHandlerCallable
from shared_domain.events.event import Event


def describe_handler(handler: Callable[..., object]) -> str:
    """Return a stable, log-friendly name for a handler.

    Kept cheap and defensive: handler names appear in every error and every log
    line, so this must never raise for an unusual callable.
    """
    if isinstance(handler, EventHandler):
        return type(handler).__name__
    receiver = getattr(handler, "__self__", None)
    name = getattr(handler, "__qualname__", None) or getattr(handler, "__name__", None)
    if receiver is not None and name is not None:
        return f"{type(receiver).__name__}.{name.rsplit('.', 1)[-1]}"
    return name or type(handler).__name__


class HandlerRegistry:
    """Maps event types to handlers, with inheritance-aware lookup.

    Two properties matter for correctness under asyncio:

    * Handler lists are immutable tuples replaced wholesale on every mutation
      (copy-on-write). A publish resolves its handlers once, then awaits them;
      a concurrent subscription can never mutate the tuple a running dispatch is
      iterating. This is why the bus needs no lock: every method here is fully
      synchronous, so it cannot be interleaved by the event loop.
    * Resolution walks the event's MRO so a handler subscribed to ``DomainEvent``
      also sees ``AuthorDeleted``. That walk happens once per event class and is
      then cached, so steady-state lookup is a single dict hit.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Event], tuple[EventHandlerCallable, ...]] = {}
        self._resolved: dict[type[Event], tuple[EventHandlerCallable, ...]] = {}

    def register[EventT: Event](
        self, event_type: type[EventT], handler: EventHandlerCallable[EventT]
    ) -> None:
        try:
            hash(handler)
        except TypeError as exc:
            # Resolution deduplicates handlers through a set, so an unhashable
            # handler would fail at publish time instead of at wiring time.
            raise TypeError(
                f"Handler {describe_handler(handler)} must be hashable to be "
                f"subscribed; it probably defines __eq__ without __hash__."
            ) from exc

        registered = self._handlers.get(event_type, ())
        if any(existing == handler for existing in registered):
            raise DuplicateHandlerError(event_type, describe_handler(handler))
        self._handlers[event_type] = (*registered, handler)
        self._invalidate()

    def unregister[EventT: Event](
        self, event_type: type[EventT], handler: EventHandlerCallable[EventT]
    ) -> None:
        registered = self._handlers.get(event_type, ())
        remaining = tuple(existing for existing in registered if existing != handler)
        if len(remaining) == len(registered):
            raise HandlerNotRegisteredError(event_type, describe_handler(handler))
        if remaining:
            self._handlers[event_type] = remaining
        else:
            del self._handlers[event_type]
        self._invalidate()

    def resolve(self, event_type: type[Event]) -> tuple[EventHandlerCallable, ...]:
        """Return the handlers for ``event_type``, most specific subscription first.

        A handler subscribed at several levels of the hierarchy is returned once,
        at its most specific position, so publishing never triggers duplicate
        side effects.
        """
        cached = self._resolved.get(event_type)
        if cached is not None:
            return cached

        resolved: list[EventHandlerCallable] = []
        seen: set[EventHandlerCallable] = set()
        for klass in event_type.__mro__:
            for handler in self._handlers.get(klass, ()):
                if handler not in seen:
                    seen.add(handler)
                    resolved.append(handler)

        snapshot = tuple(resolved)
        self._resolved[event_type] = snapshot
        return snapshot

    def clear(self) -> None:
        self._handlers = {}
        self._invalidate()

    def _invalidate(self) -> None:
        # Replaced rather than mutated so an in-flight dispatch keeps the tuple
        # it already resolved.
        self._resolved = {}
