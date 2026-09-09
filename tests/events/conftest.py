from typing import ClassVar
from uuid import uuid4

import pytest

from infrastructure.events.in_memory_event_bus import InMemoryEventBus
from shared_domain.events.event import (
    ApplicationEvent,
    DomainEvent,
    Event,
    IntegrationEvent,
)


class OrderPlaced(DomainEvent):
    """Test double for a domain event."""

    quantity: int = 1


class OrderShipped(DomainEvent):
    """A sibling domain event, used to prove dispatch is type-directed."""


class CacheInvalidated(ApplicationEvent):
    """Test double for an in-process application event."""

    key: str = "any"


class OrderPlacedIntegration(IntegrationEvent):
    event_type: ClassVar[str] = "order.placed.v1"


@pytest.fixture
def bus() -> InMemoryEventBus:
    """A fresh bus per test.

    The bus holds no module-level state, so isolation between tests is
    structural rather than something a fixture has to clean up.
    """
    return InMemoryEventBus()


@pytest.fixture
def order_placed() -> OrderPlaced:
    return OrderPlaced(aggregate_id=uuid4())


class Recorder:
    """Collects the events a handler received, in order."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def __call__(self, event: Event) -> None:
        self.events.append(event)
