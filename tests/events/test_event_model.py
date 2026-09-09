from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

import pytest
from pydantic import ValidationError

from shared_domain.events.event import DomainEvent, Event, IntegrationEvent
from tests.events.conftest import CacheInvalidated, OrderPlaced, OrderPlacedIntegration


def test_events_are_immutable():
    event = OrderPlaced(aggregate_id=uuid4())

    with pytest.raises(ValidationError):
        event.quantity = 99


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        OrderPlaced(aggregate_id=uuid4(), typo_field=1)


def test_each_event_gets_a_unique_id():
    aggregate_id = uuid4()

    first = OrderPlaced(aggregate_id=aggregate_id)
    second = OrderPlaced(aggregate_id=aggregate_id)

    assert first.event_id != second.event_id


def test_occurred_at_is_timezone_aware_utc():
    before = datetime.now(UTC)

    event = OrderPlaced(aggregate_id=uuid4())

    assert event.occurred_at.tzinfo is not None
    assert before <= event.occurred_at <= datetime.now(UTC)


def test_root_event_correlates_to_itself():
    event = OrderPlaced(aggregate_id=uuid4())

    assert event.correlation_id == event.event_id
    assert event.causation_id is None


def test_explicit_correlation_id_is_preserved():
    correlation_id = uuid4()

    event = OrderPlaced(aggregate_id=uuid4(), correlation_id=correlation_id)

    assert event.correlation_id == correlation_id


def test_caused_by_links_a_chain_under_one_correlation_id():
    root = OrderPlaced(aggregate_id=uuid4())

    child = CacheInvalidated(key="orders").caused_by(root)
    grandchild = CacheInvalidated(key="totals").caused_by(child)

    assert child.correlation_id == root.correlation_id
    assert child.causation_id == root.event_id
    assert grandchild.correlation_id == root.correlation_id
    assert grandchild.causation_id == child.event_id


def test_caused_by_does_not_mutate_either_event():
    root = OrderPlaced(aggregate_id=uuid4())
    child = CacheInvalidated(key="orders")

    derived = child.caused_by(root)

    assert child.causation_id is None
    assert derived is not child
    assert root.causation_id is None


def test_event_type_defaults_to_the_class_name():
    assert OrderPlaced.event_type == "OrderPlaced"


def test_event_type_can_be_declared_explicitly():
    class RenamedEvent(DomainEvent):
        event_type: ClassVar[str] = "order.renamed"

    assert RenamedEvent.event_type == "order.renamed"


def test_integration_events_must_declare_a_wire_name():
    with pytest.raises(TypeError, match="must declare an explicit"):

        class Unnamed(IntegrationEvent):
            pass


def test_integration_event_with_a_wire_name_is_valid():
    assert OrderPlacedIntegration.event_type == "order.placed.v1"
    assert OrderPlacedIntegration.event_version == 1


def test_events_serialise_to_plain_data():
    event = OrderPlaced(aggregate_id=uuid4(), quantity=3)

    dumped = event.model_dump(mode="json")

    assert dumped["quantity"] == 3
    assert dumped["event_id"] == str(event.event_id)
    assert dumped["aggregate_id"] == str(event.aggregate_id)
    assert OrderPlaced.model_validate(dumped) == event


def test_event_categories_share_one_root():
    assert issubclass(OrderPlaced, Event)
    assert issubclass(CacheInvalidated, Event)
    assert issubclass(OrderPlacedIntegration, Event)
    assert not issubclass(CacheInvalidated, DomainEvent)
