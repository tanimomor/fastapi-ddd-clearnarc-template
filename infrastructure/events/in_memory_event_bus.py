import asyncio
import logging
import time
from collections.abc import Sequence

from application.events.exceptions import (
    EventBusClosedError,
    EventDispatchError,
    HandlerFailure,
    HandlerTimeoutError,
    IntegrationEventNotSupportedError,
)
from application.events.interface import EventHandlerCallable, IEventBus
from infrastructure.events.registry import HandlerRegistry, describe_handler
from shared_domain.events.event import Event, IntegrationEvent

logger = logging.getLogger(__name__)


class InMemoryEventBus(IEventBus):
    """Single-process, in-memory event bus.

    Execution semantics
    -------------------
    Handlers run **sequentially, in registration order, awaited inside the
    publisher's own task**. That is the safest default for a request-scoped web
    process:

    * it is deterministic and therefore reproducible in tests and in incidents;
    * handlers inherit the caller's context (contextvars, request scope, the
      surrounding cancellation scope), so tracing and cancellation stay intact;
    * it creates no background tasks, so nothing can leak or be silently dropped
      at shutdown;
    * it bounds load: N concurrent requests cause N concurrent handlers, not
      N x handlers hitting the database pool at once.

    Running handlers concurrently would buy very little (handler counts are
    small) at the cost of nondeterminism and unbounded fan-out, so it is not
    offered. Work that genuinely must not block the caller belongs in a task
    queue, not in an in-memory bus.

    Guarantees
    ----------
    Honest list of what this bus provides: in-order, at-most-once, best-effort,
    in-process delivery to the handlers registered at the moment of publication,
    with per-handler failure isolation and aggregated error reporting. It
    provides **no** durability, no retries, no delivery across processes and no
    transactional coupling to the database. If the process dies between a commit
    and a handler, that work is simply lost - see the module docs in
    ``api/events.py`` for where an outbox becomes necessary.
    """

    def __init__(
        self,
        *,
        handler_timeout: float | None = None,
        shutdown_drain_timeout: float = 5.0,
    ) -> None:
        """
        :param handler_timeout: optional per-handler ceiling in seconds. Off by
            default: the HTTP server already bounds request duration, and an
            arbitrary default would silently break legitimately slow handlers.
            Set it when handlers do I/O that can hang.
        :param shutdown_drain_timeout: how long :meth:`aclose` waits for
            in-flight dispatches before giving up and logging.
        """
        self._registry = HandlerRegistry()
        self._handler_timeout = handler_timeout
        self._shutdown_drain_timeout = shutdown_drain_timeout
        self._closed = False
        self._in_flight = 0
        self._idle = asyncio.Event()
        self._idle.set()

    # -- registration ----------------------------------------------------

    def subscribe[EventT: Event](
        self, event_type: type[EventT], handler: EventHandlerCallable[EventT]
    ) -> None:
        self._guard_open("subscribe")
        self._guard_event_type(event_type)
        self._registry.register(event_type, handler)
        logger.debug(
            "Event handler subscribed",
            extra={"event_type": event_type.event_type, "handler": describe_handler(handler)},
        )

    def unsubscribe[EventT: Event](
        self, event_type: type[EventT], handler: EventHandlerCallable[EventT]
    ) -> None:
        self._registry.unregister(event_type, handler)
        logger.debug(
            "Event handler unsubscribed",
            extra={"event_type": event_type.event_type, "handler": describe_handler(handler)},
        )

    # -- publishing ------------------------------------------------------

    async def publish(self, event: Event) -> None:
        await self.publish_many((event,))

    async def publish_many(self, events: Sequence[Event]) -> None:
        if not events:
            return

        self._guard_open("publish")
        # Validated up front so a batch containing an unsupported event fails
        # before any handler has run and produced side effects.
        for event in events:
            self._guard_event_type(type(event))

        failures: list[HandlerFailure] = []
        self._enter_flight()
        try:
            for event in events:
                failures.extend(await self._dispatch(event))
        finally:
            self._exit_flight()

        if failures:
            raise EventDispatchError(failures)

    async def _dispatch(self, event: Event) -> list[HandlerFailure]:
        # Resolved once: handlers subscribed after this point do not observe
        # this event, and handlers unsubscribed after this point still run.
        handlers = self._registry.resolve(type(event))
        if not handlers:
            logger.debug("Event published with no handlers", extra=self._context(event))
            return []

        failures: list[HandlerFailure] = []
        for handler in handlers:
            failure = await self._invoke(handler, event)
            if failure is not None:
                failures.append(failure)
        return failures

    async def _invoke(
        self, handler: EventHandlerCallable, event: Event
    ) -> HandlerFailure | None:
        handler_name = describe_handler(handler)
        context = self._context(event, handler=handler_name)
        started = time.perf_counter()

        try:
            if self._handler_timeout is None:
                await handler(event)
            else:
                timeout = asyncio.timeout(self._handler_timeout)
                try:
                    async with timeout:
                        await handler(event)
                except TimeoutError as exc:
                    if not timeout.expired():
                        raise
                    raise HandlerTimeoutError(handler_name, self._handler_timeout) from exc
        except asyncio.CancelledError:
            # The caller is going away (client disconnect, shutdown, an outer
            # timeout). Cancellation is not a handler failure: propagate it
            # immediately and abandon the remaining handlers rather than
            # swallowing it or continuing work nobody is waiting for.
            logger.warning(
                "Event handler cancelled",
                extra={**context, "outcome": "cancelled", **self._elapsed(started)},
            )
            raise
        except Exception as exc:
            logger.exception(
                "Event handler failed",
                extra={**context, "outcome": "failed", **self._elapsed(started)},
            )
            return HandlerFailure(event, handler_name, exc)

        logger.debug(
            "Event handler succeeded",
            extra={**context, "outcome": "succeeded", **self._elapsed(started)},
        )
        return None

    # -- lifecycle -------------------------------------------------------

    async def aclose(self) -> None:
        """Idempotent shutdown: reject new work, drain in-flight, drop handlers.

        Because dispatch is awaited by the publisher, in-flight work is normally
        already finished by the time the HTTP server has drained its requests.
        Draining here also covers publishes started by application-owned
        background tasks.
        """
        if self._closed:
            return
        self._closed = True

        if self._in_flight:
            try:
                async with asyncio.timeout(self._shutdown_drain_timeout):
                    await self._idle.wait()
            except TimeoutError:
                logger.warning(
                    "Event bus shut down with dispatches still in flight",
                    extra={"in_flight": self._in_flight},
                )

        # Dropping registrations releases the handlers' collaborators; without
        # this a long-lived bus would pin every injected dependency.
        self._registry.clear()
        logger.info("Event bus closed")

    @property
    def is_closed(self) -> bool:
        return self._closed

    # -- internals -------------------------------------------------------

    def _guard_open(self, operation: str) -> None:
        if self._closed:
            raise EventBusClosedError(operation)

    @staticmethod
    def _guard_event_type(event_type: type[Event]) -> None:
        if not (isinstance(event_type, type) and issubclass(event_type, Event)):
            raise TypeError(f"{event_type!r} is not an Event subclass")
        if issubclass(event_type, IntegrationEvent):
            raise IntegrationEventNotSupportedError(event_type)

    # In-flight accounting needs no lock. Every mutation below is synchronous,
    # and `publish_many` runs its guards and `_enter_flight` with no await in
    # between, so a publish is either counted before `aclose` observes the count
    # or rejected by the closed check - there is no window between the two.
    def _enter_flight(self) -> None:
        self._in_flight += 1
        self._idle.clear()

    def _exit_flight(self) -> None:
        self._in_flight -= 1
        if self._in_flight == 0:
            self._idle.set()

    @staticmethod
    def _context(event: Event, **extra: object) -> dict[str, object]:
        """Structured log context.

        Deliberately identifiers only - never the event payload, which routinely
        carries personal or otherwise sensitive data.
        """
        return {
            "event_type": type(event).event_type,
            "event_id": str(event.event_id),
            "correlation_id": str(event.correlation_id),
            "causation_id": str(event.causation_id) if event.causation_id else None,
            "aggregate_id": str(aggregate_id)
            if (aggregate_id := getattr(event, "aggregate_id", None))
            else None,
            **extra,
        }

    @staticmethod
    def _elapsed(started: float) -> dict[str, float]:
        return {"duration_ms": round((time.perf_counter() - started) * 1000, 3)}
