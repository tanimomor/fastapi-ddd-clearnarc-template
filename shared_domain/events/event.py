from datetime import UTC, datetime
from typing import Any, ClassVar, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Event(BaseModel):
    """Root of the event hierarchy.

    Domains never subclass this directly: they pick one of the three
    categories below, which carry different rules about who may consume them.

    Every event is immutable and self-describing. The envelope is intentionally
    small - only the fields that cannot be reconstructed by a consumer are
    carried here. There is deliberately no free-form ``metadata`` dict: it is an
    escape hatch that invites untyped coupling between modules and leaks payload
    data into logs. Anything a consumer needs belongs in a typed field on the
    concrete event.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: ClassVar[str] = "Event"
    """Stable logical name of the event, used for logging and type resolution.

    Defaults to the class name. Events that will ever cross a process boundary
    must declare this explicitly so renaming the class does not break consumers.
    """

    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None
    """Identifies the whole causal chain this event belongs to.

    A root event correlates to itself, so this is never ``None`` after
    construction and every derived event shares the originator's value.
    """
    causation_id: UUID | None = None
    """``event_id`` of the event that directly caused this one, if any."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        if "event_type" not in cls.__dict__:
            cls.event_type = cls.__name__

    @model_validator(mode="after")
    def _default_correlation_to_self(self) -> Self:
        if self.correlation_id is None:
            object.__setattr__(self, "correlation_id", self.event_id)
        return self

    def caused_by(self, parent: "Event") -> Self:
        """Return a copy of this event linked to the event that caused it.

        Used by a handler that reacts to an event by publishing another one, so
        the whole chain stays traceable under a single ``correlation_id``::

            await publisher.publish(BooksArchived(...).caused_by(event))
        """
        return self.model_copy(
            update={
                "correlation_id": parent.correlation_id,
                "causation_id": parent.event_id,
            }
        )


class DomainEvent(Event):
    """A fact that occurred inside a single domain, named in the past tense.

    Domain events are part of the domain's published language: other modules may
    subscribe to them, but they are not a public API contract outside the
    process. They always describe a change to one aggregate.
    """

    aggregate_id: UUID


class ApplicationEvent(Event):
    """An in-process notification that is not a domain fact.

    Use for infrastructure-flavoured signals that must not pollute the domain
    language (cache invalidation, a projection rebuild request, an audit hook).
    """


class IntegrationEvent(Event):
    """A contract published to *other processes*.

    Integration events are versioned wire contracts, so they must declare an
    explicit ``event_type``. The in-memory bus deliberately refuses to publish
    them: delivering an integration event in-process would silently pretend that
    a durable transport exists. Publishing one requires a real broker plus an
    outbox, introduced behind its own interface.
    """

    event_version: ClassVar[int] = 1

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        # Checked before delegating: the base hook would otherwise fill in a
        # default ``event_type`` and hide the missing wire contract.
        if "event_type" not in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} is an IntegrationEvent and must declare an explicit "
                f'`event_type: ClassVar[str]` (for example "author.deleted.v1"), '
                f"because its name is a wire contract."
            )
        super().__pydantic_init_subclass__(**kwargs)
