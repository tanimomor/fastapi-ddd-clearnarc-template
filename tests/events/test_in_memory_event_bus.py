import asyncio
from uuid import uuid4

import pytest

from application.events.exceptions import (
    DuplicateHandlerError,
    EventBusClosedError,
    EventDispatchError,
    HandlerNotRegisteredError,
    HandlerTimeoutError,
    IntegrationEventNotSupportedError,
)
from application.events.interface import EventHandler
from infrastructure.events.in_memory_event_bus import InMemoryEventBus
from shared_domain.events.event import DomainEvent, Event
from tests.events.conftest import (
    CacheInvalidated,
    OrderPlaced,
    OrderPlacedIntegration,
    OrderShipped,
    Recorder,
)

# --- delivery ------------------------------------------------------------


async def test_a_subscribed_handler_receives_the_published_event(bus, order_placed):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)

    await bus.publish(order_placed)

    assert recorder.events == [order_placed]


async def test_the_handler_receives_the_exact_event_instance(bus, order_placed):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)

    await bus.publish(order_placed)

    received = recorder.events[0]
    assert received is order_placed
    assert received.event_id == order_placed.event_id
    assert received.correlation_id == order_placed.correlation_id


async def test_every_subscribed_handler_receives_the_event(bus, order_placed):
    first, second, third = Recorder(), Recorder(), Recorder()
    for recorder in (first, second, third):
        bus.subscribe(OrderPlaced, recorder)

    await bus.publish(order_placed)

    assert [len(r.events) for r in (first, second, third)] == [1, 1, 1]


async def test_handlers_run_in_registration_order(bus, order_placed):
    order: list[str] = []

    async def first(_event: Event) -> None:
        order.append("first")

    async def second(_event: Event) -> None:
        order.append("second")

    async def third(_event: Event) -> None:
        order.append("third")

    bus.subscribe(OrderPlaced, first)
    bus.subscribe(OrderPlaced, second)
    bus.subscribe(OrderPlaced, third)

    await bus.publish(order_placed)

    assert order == ["first", "second", "third"]


async def test_handlers_of_one_event_do_not_overlap(bus, order_placed):
    """Dispatch is sequential, so a handler always completes before the next starts."""
    timeline: list[str] = []

    async def slow(_event: Event) -> None:
        timeline.append("slow:start")
        await asyncio.sleep(0.01)
        timeline.append("slow:end")

    async def fast(_event: Event) -> None:
        timeline.append("fast:start")
        timeline.append("fast:end")

    bus.subscribe(OrderPlaced, slow)
    bus.subscribe(OrderPlaced, fast)

    await bus.publish(order_placed)

    assert timeline == ["slow:start", "slow:end", "fast:start", "fast:end"]


async def test_publish_returns_only_after_handlers_finished(bus, order_placed):
    finished = False

    async def handler(_event: Event) -> None:
        nonlocal finished
        await asyncio.sleep(0.01)
        finished = True

    bus.subscribe(OrderPlaced, handler)

    await bus.publish(order_placed)

    assert finished is True


async def test_an_event_with_no_handlers_is_not_an_error(bus, order_placed):
    await bus.publish(order_placed)


# --- typed dispatch ------------------------------------------------------


async def test_handlers_only_receive_the_event_type_they_subscribed_to(bus):
    placed, shipped = Recorder(), Recorder()
    bus.subscribe(OrderPlaced, placed)
    bus.subscribe(OrderShipped, shipped)

    await bus.publish(OrderPlaced(aggregate_id=uuid4()))

    assert len(placed.events) == 1
    assert shipped.events == []


async def test_subscribing_to_a_base_type_receives_subclasses(bus):
    """An audit-style handler can subscribe once to a whole category."""
    audit = Recorder()
    bus.subscribe(DomainEvent, audit)

    await bus.publish(OrderPlaced(aggregate_id=uuid4()))
    await bus.publish(OrderShipped(aggregate_id=uuid4()))
    await bus.publish(CacheInvalidated(key="k"))

    assert [type(event) for event in audit.events] == [OrderPlaced, OrderShipped]


async def test_specific_handlers_run_before_base_type_handlers(bus, order_placed):
    order: list[str] = []

    async def specific(_event: Event) -> None:
        order.append("specific")

    async def base(_event: Event) -> None:
        order.append("base")

    async def root(_event: Event) -> None:
        order.append("root")

    bus.subscribe(Event, root)
    bus.subscribe(DomainEvent, base)
    bus.subscribe(OrderPlaced, specific)

    await bus.publish(order_placed)

    assert order == ["specific", "base", "root"]


async def test_a_handler_subscribed_at_two_levels_runs_once(bus, order_placed):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)
    bus.subscribe(DomainEvent, recorder)

    await bus.publish(order_placed)

    assert len(recorder.events) == 1


# --- publish_many --------------------------------------------------------


async def test_publish_many_dispatches_every_event_in_order(bus):
    recorder = Recorder()
    bus.subscribe(DomainEvent, recorder)
    events = [OrderPlaced(aggregate_id=uuid4()) for _ in range(3)]

    await bus.publish_many(events)

    assert recorder.events == events


async def test_publish_many_with_no_events_is_a_no_op(bus):
    recorder = Recorder()
    bus.subscribe(DomainEvent, recorder)

    await bus.publish_many([])

    assert recorder.events == []


async def test_publish_many_continues_after_a_failing_event(bus):
    recorder = Recorder()

    async def explode(event: Event) -> None:
        if getattr(event, "quantity", 0) == 1:
            raise ValueError("boom")

    bus.subscribe(DomainEvent, explode)
    bus.subscribe(DomainEvent, recorder)
    failing = OrderPlaced(aggregate_id=uuid4(), quantity=1)
    following = OrderPlaced(aggregate_id=uuid4(), quantity=2)

    with pytest.raises(EventDispatchError):
        await bus.publish_many([failing, following])

    assert recorder.events == [failing, following]


# --- failure semantics ---------------------------------------------------


async def test_one_failing_handler_does_not_stop_the_others(bus, order_placed):
    before, after = Recorder(), Recorder()

    async def failing(_event: Event) -> None:
        raise ValueError("boom")

    bus.subscribe(OrderPlaced, before)
    bus.subscribe(OrderPlaced, failing)
    bus.subscribe(OrderPlaced, after)

    with pytest.raises(EventDispatchError):
        await bus.publish(order_placed)

    assert len(before.events) == 1
    assert len(after.events) == 1


async def test_handler_failures_are_reported_not_swallowed(bus, order_placed):
    async def failing(_event: Event) -> None:
        raise ValueError("boom")

    bus.subscribe(OrderPlaced, failing)

    with pytest.raises(EventDispatchError) as exc_info:
        await bus.publish(order_placed)

    error = exc_info.value
    assert [type(exc) for exc in error.exceptions] == [ValueError]
    assert error.failures[0].handler_name.endswith("failing")
    assert error.failures[0].event is order_placed


async def test_all_failures_are_aggregated(bus, order_placed):
    async def fails_with_value_error(_event: Event) -> None:
        raise ValueError("boom")

    async def fails_with_key_error(_event: Event) -> None:
        raise KeyError("missing")

    bus.subscribe(OrderPlaced, fails_with_value_error)
    bus.subscribe(OrderPlaced, fails_with_key_error)

    with pytest.raises(EventDispatchError) as exc_info:
        await bus.publish(order_placed)

    assert {type(exc) for exc in exc_info.value.exceptions} == {ValueError, KeyError}


async def test_failures_can_be_selected_with_except_star(bus, order_placed):
    async def fails_with_value_error(_event: Event) -> None:
        raise ValueError("boom")

    async def fails_with_key_error(_event: Event) -> None:
        raise KeyError("missing")

    bus.subscribe(OrderPlaced, fails_with_value_error)
    bus.subscribe(OrderPlaced, fails_with_key_error)

    caught: list[BaseException] = []
    try:
        await bus.publish(order_placed)
    except* ValueError as group:
        caught.extend(group.exceptions)
    except* KeyError as group:
        caught.extend(group.exceptions)

    assert {type(exc) for exc in caught} == {ValueError, KeyError}


async def test_original_traceback_is_preserved(bus, order_placed):
    async def failing(_event: Event) -> None:
        raise ValueError("boom")

    bus.subscribe(OrderPlaced, failing)

    with pytest.raises(EventDispatchError) as exc_info:
        await bus.publish(order_placed)

    assert exc_info.value.exceptions[0].__traceback__ is not None


async def test_failures_are_logged_with_context_but_not_the_payload(
    bus, order_placed, caplog
):
    async def failing(_event: Event) -> None:
        raise ValueError("secret-payload-must-not-leak")

    bus.subscribe(OrderPlaced, failing)

    with caplog.at_level("ERROR"), pytest.raises(EventDispatchError):
        await bus.publish(order_placed)

    record = next(r for r in caplog.records if r.message == "Event handler failed")
    assert record.event_type == "OrderPlaced"
    assert record.event_id == str(order_placed.event_id)
    assert record.correlation_id == str(order_placed.correlation_id)
    assert record.handler.endswith("failing")
    assert record.outcome == "failed"
    assert record.duration_ms >= 0
    assert "quantity" not in record.getMessage()


# --- cancellation --------------------------------------------------------


async def test_cancellation_propagates_and_stops_remaining_handlers(bus, order_placed):
    started = asyncio.Event()
    later_ran = False

    async def blocking(_event: Event) -> None:
        started.set()
        await asyncio.sleep(3600)

    async def later(_event: Event) -> None:
        nonlocal later_ran
        later_ran = True

    bus.subscribe(OrderPlaced, blocking)
    bus.subscribe(OrderPlaced, later)

    task = asyncio.create_task(bus.publish(order_placed))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert later_ran is False


async def test_cancellation_is_not_reported_as_a_handler_failure(bus, order_placed):
    started = asyncio.Event()

    async def blocking(_event: Event) -> None:
        started.set()
        await asyncio.sleep(3600)

    bus.subscribe(OrderPlaced, blocking)

    task = asyncio.create_task(bus.publish(order_placed))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError) as exc_info:
        await task
    assert not isinstance(exc_info.value, EventDispatchError)


# --- timeouts ------------------------------------------------------------


async def test_handlers_are_not_time_limited_by_default(bus, order_placed):
    async def slow(_event: Event) -> None:
        await asyncio.sleep(0.05)

    bus.subscribe(OrderPlaced, slow)

    await bus.publish(order_placed)


async def test_a_hanging_handler_is_timed_out_when_configured(order_placed):
    bus = InMemoryEventBus(handler_timeout=0.01)
    after = Recorder()

    async def hanging(_event: Event) -> None:
        await asyncio.sleep(3600)

    bus.subscribe(OrderPlaced, hanging)
    bus.subscribe(OrderPlaced, after)

    with pytest.raises(EventDispatchError) as exc_info:
        await bus.publish(order_placed)

    assert isinstance(exc_info.value.exceptions[0], HandlerTimeoutError)
    assert len(after.events) == 1, "later handlers still run after a timeout"


async def test_a_handler_raising_timeout_error_is_an_ordinary_failure(order_placed):
    bus = InMemoryEventBus(handler_timeout=10)

    async def failing(_event: Event) -> None:
        raise TimeoutError("the handler's own upstream call timed out")

    bus.subscribe(OrderPlaced, failing)

    with pytest.raises(EventDispatchError) as exc_info:
        await bus.publish(order_placed)

    failure = exc_info.value.exceptions[0]
    assert isinstance(failure, TimeoutError)
    assert not isinstance(failure, HandlerTimeoutError)


# --- registration --------------------------------------------------------


async def test_registering_the_same_handler_twice_is_rejected(bus):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)

    with pytest.raises(DuplicateHandlerError):
        bus.subscribe(OrderPlaced, recorder)


async def test_a_rejected_duplicate_does_not_double_dispatch(bus, order_placed):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)
    with pytest.raises(DuplicateHandlerError):
        bus.subscribe(OrderPlaced, recorder)

    await bus.publish(order_placed)

    assert len(recorder.events) == 1


async def test_the_same_handler_can_serve_different_event_types(bus):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)
    bus.subscribe(OrderShipped, recorder)

    await bus.publish(OrderPlaced(aggregate_id=uuid4()))
    await bus.publish(OrderShipped(aggregate_id=uuid4()))

    assert len(recorder.events) == 2


async def test_an_unsubscribed_handler_stops_receiving_events(bus, order_placed):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)
    bus.unsubscribe(OrderPlaced, recorder)

    await bus.publish(order_placed)

    assert recorder.events == []


async def test_unsubscribing_leaves_other_handlers_registered(bus, order_placed):
    removed, kept = Recorder(), Recorder()
    bus.subscribe(OrderPlaced, removed)
    bus.subscribe(OrderPlaced, kept)

    bus.unsubscribe(OrderPlaced, removed)
    await bus.publish(order_placed)

    assert removed.events == []
    assert len(kept.events) == 1


async def test_unsubscribing_an_unknown_handler_is_rejected(bus):
    with pytest.raises(HandlerNotRegisteredError):
        bus.unsubscribe(OrderPlaced, Recorder())


async def test_resubscribing_after_unsubscribing_works(bus, order_placed):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)
    bus.unsubscribe(OrderPlaced, recorder)
    bus.subscribe(OrderPlaced, recorder)

    await bus.publish(order_placed)

    assert len(recorder.events) == 1


async def test_class_based_handlers_are_supported(bus, order_placed):
    class RecordingHandler(EventHandler[OrderPlaced]):
        def __init__(self) -> None:
            self.received: list[OrderPlaced] = []

        async def handle(self, event: OrderPlaced) -> None:
            self.received.append(event)

    handler = RecordingHandler()
    bus.subscribe(OrderPlaced, handler)

    await bus.publish(order_placed)

    assert handler.received == [order_placed]


async def test_bound_methods_are_supported(bus, order_placed):
    class Service:
        def __init__(self) -> None:
            self.received: list[Event] = []

        async def on_order_placed(self, event: Event) -> None:
            self.received.append(event)

    service = Service()
    bus.subscribe(OrderPlaced, service.on_order_placed)

    await bus.publish(order_placed)

    assert len(service.received) == 1


# --- registration racing publication -------------------------------------


async def test_a_handler_subscribed_during_dispatch_misses_the_current_event(
    bus, order_placed
):
    """Each publish is dispatched to the handler set resolved when it started."""
    late = Recorder()

    async def subscriber(_event: Event) -> None:
        try:
            bus.subscribe(OrderPlaced, late)
        except DuplicateHandlerError:
            pass

    bus.subscribe(OrderPlaced, subscriber)

    await bus.publish(order_placed)
    assert late.events == []

    await bus.publish(OrderPlaced(aggregate_id=uuid4()))
    assert len(late.events) == 1


async def test_a_handler_unsubscribed_during_dispatch_still_runs_for_that_event(
    bus, order_placed
):
    doomed = Recorder()

    async def unsubscriber(_event: Event) -> None:
        try:
            bus.unsubscribe(OrderPlaced, doomed)
        except HandlerNotRegisteredError:
            pass

    bus.subscribe(OrderPlaced, unsubscriber)
    bus.subscribe(OrderPlaced, doomed)

    await bus.publish(order_placed)

    assert len(doomed.events) == 1, "the resolved snapshot is stable for the dispatch"

    await bus.publish(OrderPlaced(aggregate_id=uuid4()))
    assert len(doomed.events) == 1


async def test_subscribing_while_a_publish_is_awaiting_is_safe(bus, order_placed):
    started = asyncio.Event()
    release = asyncio.Event()
    late = Recorder()

    async def slow(_event: Event) -> None:
        started.set()
        await release.wait()

    bus.subscribe(OrderPlaced, slow)
    task = asyncio.create_task(bus.publish(order_placed))
    await started.wait()

    bus.subscribe(OrderPlaced, late)
    release.set()
    await task

    assert late.events == []


# --- concurrent publishing ------------------------------------------------


async def test_concurrent_publishes_all_reach_their_handlers(bus):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)
    events = [OrderPlaced(aggregate_id=uuid4()) for _ in range(50)]

    await asyncio.gather(*(bus.publish(event) for event in events))

    assert len(recorder.events) == 50
    assert {event.event_id for event in recorder.events} == {e.event_id for e in events}


async def test_a_failing_publish_does_not_affect_a_concurrent_one(bus):
    succeeded = Recorder()

    async def fail_on_odd_quantity(event: Event) -> None:
        if getattr(event, "quantity", 0) % 2 == 1:
            raise ValueError("boom")
        await succeeded(event)

    bus.subscribe(OrderPlaced, fail_on_odd_quantity)
    good = OrderPlaced(aggregate_id=uuid4(), quantity=2)
    bad = OrderPlaced(aggregate_id=uuid4(), quantity=1)

    results = await asyncio.gather(
        bus.publish(good), bus.publish(bad), return_exceptions=True
    )

    assert results[0] is None
    assert isinstance(results[1], EventDispatchError)
    assert succeeded.events == [good]


# --- integration events ---------------------------------------------------


async def test_the_in_memory_bus_refuses_to_publish_integration_events(bus):
    with pytest.raises(IntegrationEventNotSupportedError):
        await bus.publish(OrderPlacedIntegration())


async def test_the_in_memory_bus_refuses_integration_event_subscriptions(bus):
    with pytest.raises(IntegrationEventNotSupportedError):
        bus.subscribe(OrderPlacedIntegration, Recorder())


async def test_a_rejected_batch_dispatches_nothing(bus):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)

    with pytest.raises(IntegrationEventNotSupportedError):
        await bus.publish_many(
            [OrderPlaced(aggregate_id=uuid4()), OrderPlacedIntegration()]
        )

    assert recorder.events == [], "validation happens before any side effect"


# --- lifecycle ------------------------------------------------------------


async def test_a_closed_bus_refuses_to_publish(bus, order_placed):
    await bus.aclose()

    with pytest.raises(EventBusClosedError):
        await bus.publish(order_placed)


async def test_a_closed_bus_refuses_new_subscriptions(bus):
    await bus.aclose()

    with pytest.raises(EventBusClosedError):
        bus.subscribe(OrderPlaced, Recorder())


async def test_closing_releases_handler_references(bus, order_placed):
    recorder = Recorder()
    bus.subscribe(OrderPlaced, recorder)

    await bus.aclose()

    assert bus.is_closed is True
    with pytest.raises(HandlerNotRegisteredError):
        bus.unsubscribe(OrderPlaced, recorder)


async def test_closing_twice_is_safe(bus):
    await bus.aclose()
    await bus.aclose()

    assert bus.is_closed is True


async def test_close_waits_for_an_in_flight_dispatch(bus, order_placed):
    started = asyncio.Event()
    release = asyncio.Event()
    completed = False

    async def slow(_event: Event) -> None:
        nonlocal completed
        started.set()
        await release.wait()
        completed = True

    bus.subscribe(OrderPlaced, slow)
    publish_task = asyncio.create_task(bus.publish(order_placed))
    await started.wait()

    close_task = asyncio.create_task(bus.aclose())
    await asyncio.sleep(0)
    assert not close_task.done(), "close must not abandon in-flight work"

    release.set()
    await publish_task
    await close_task

    assert completed is True


async def test_close_gives_up_on_a_stuck_dispatch_after_the_drain_timeout(order_placed):
    bus = InMemoryEventBus(shutdown_drain_timeout=0.01)
    started = asyncio.Event()

    async def hanging(_event: Event) -> None:
        started.set()
        await asyncio.sleep(3600)

    bus.subscribe(OrderPlaced, hanging)
    publish_task = asyncio.create_task(bus.publish(order_placed))
    await started.wait()

    await bus.aclose()

    assert bus.is_closed is True
    publish_task.cancel()


# --- isolation ------------------------------------------------------------


async def test_two_buses_do_not_share_handlers(order_placed):
    first_bus, second_bus = InMemoryEventBus(), InMemoryEventBus()
    recorder = Recorder()
    first_bus.subscribe(OrderPlaced, recorder)

    await second_bus.publish(order_placed)

    assert recorder.events == []


async def test_subscribing_to_a_non_event_type_is_rejected(bus):
    class NotAnEvent:
        pass

    with pytest.raises(TypeError, match="not an Event subclass"):
        bus.subscribe(NotAnEvent, Recorder())


async def test_subscribing_an_unhashable_handler_is_rejected_at_wiring_time(bus):
    class UnhashableHandler(EventHandler[OrderPlaced]):
        __hash__ = None  # type: ignore[assignment]

        async def handle(self, event: OrderPlaced) -> None: ...

    with pytest.raises(TypeError, match="must be hashable"):
        bus.subscribe(OrderPlaced, UnhashableHandler())
