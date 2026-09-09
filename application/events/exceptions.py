from collections.abc import Sequence

from shared_domain.events.event import Event


class EventBusError(Exception):
    """Base class for every failure raised by the event bus itself."""


class EventBusClosedError(EventBusError):
    def __init__(self, operation: str):
        super().__init__(f"Cannot {operation}: the event bus is closed")


class DuplicateHandlerError(EventBusError):
    def __init__(self, event_type: type[Event], handler_name: str):
        super().__init__(
            f"Handler {handler_name} is already subscribed to {event_type.__name__}"
        )


class HandlerNotRegisteredError(EventBusError):
    def __init__(self, event_type: type[Event], handler_name: str):
        super().__init__(
            f"Handler {handler_name} is not subscribed to {event_type.__name__}"
        )


class IntegrationEventNotSupportedError(EventBusError):
    def __init__(self, event_type: type[Event]):
        super().__init__(
            f"{event_type.__name__} is an IntegrationEvent and cannot be published on "
            f"the in-memory bus, which offers no durability, no retries and no delivery "
            f"beyond this process. Publish it through a broker-backed publisher instead."
        )


class HandlerTimeoutError(EventBusError):
    def __init__(self, handler_name: str, timeout: float):
        super().__init__(f"Handler {handler_name} exceeded its {timeout}s timeout")


class HandlerFailure:
    """A single handler failure, kept with enough context to debug it."""

    __slots__ = ("event", "handler_name", "exception")

    def __init__(self, event: Event, handler_name: str, exception: BaseException):
        self.event = event
        self.handler_name = handler_name
        self.exception = exception

    def __repr__(self) -> str:
        return (
            f"HandlerFailure(handler={self.handler_name!r}, "
            f"event={type(self.event).event_type!r}, "
            f"event_id={self.event.event_id}, "
            f"exception={self.exception!r})"
        )


class EventDispatchError(EventBusError, ExceptionGroup[BaseException]):
    """Raised when one or more handlers failed during a publish.

    Every subscribed handler still ran: the failures are isolated from each other
    and reported together. This is an ``ExceptionGroup``, so callers can use
    ``except*`` to select the failures they actually know how to deal with, and
    every original traceback is preserved.
    """

    failures: tuple[HandlerFailure, ...]

    def __new__(cls, failures: Sequence[HandlerFailure]):
        summary = ", ".join(
            f"{failure.handler_name} ({type(failure.exception).__name__})"
            for failure in failures
        )
        message = f"{len(failures)} event handler(s) failed: {summary}"
        instance = super().__new__(cls, message, [failure.exception for failure in failures])
        instance.failures = tuple(failures)
        return instance

    def derive(self, excs: Sequence[BaseException]) -> "EventDispatchError":
        by_exception = {id(failure.exception): failure for failure in self.failures}
        return EventDispatchError(
            [by_exception[id(exc)] for exc in excs if id(exc) in by_exception]
        )
