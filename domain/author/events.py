from shared_domain.events.event import DomainEvent


class AuthorDeleted(DomainEvent):
    """An author was removed from the catalogue.

    ``aggregate_id`` is the author's id. The event carries nothing else on
    purpose: consumers that need author details must react to events published
    while the author still existed, not reconstruct a deleted record from an
    envelope.
    """
