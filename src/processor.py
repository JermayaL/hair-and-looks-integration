"""Intentie-filtering en merging logica.

Logica (gebaseerd op Sven's Pilarrr → Klaviyo koppeling):
- Per unieke email worden alle intenties en afspraken samengevoegd.
- Als er minimaal 1 afspraak is → event = "appointmentMade"
- Als er alleen intenties zijn (zonder afspraak) → event = "appointmentIntention"
- De meest recente/relevante gegevens worden gebruikt voor het profiel.
"""

import logging
from collections import defaultdict

from src.models import BufferedIntention, IntentionType, ProcessedContact

logger = logging.getLogger(__name__)


def aggregate_intentions(intentions: list[BufferedIntention]) -> list[ProcessedContact]:
    """Aggregeer een lijst intenties per unieke email.

    Returns:
        Lijst van ProcessedContact objecten klaar voor Klaviyo.
    """
    if not intentions:
        return []

    # Groepeer per email
    by_email: dict[str, list[BufferedIntention]] = defaultdict(list)
    for intention in intentions:
        if intention.email:
            by_email[intention.email.lower().strip()].append(intention)

    contacts: list[ProcessedContact] = []

    for email, records in by_email.items():
        intention_count = sum(1 for r in records if r.intention_type == IntentionType.INTENTION)
        appointment_count = sum(1 for r in records if r.intention_type == IntentionType.APPOINTMENT)

        # Bepaal event type
        if appointment_count > 0:
            event_name = "appointmentMade"
        else:
            event_name = "appointmentIntention"

        # Gebruik de meest recente record voor profielgegevens
        latest = max(records, key=lambda r: r.created_at or r.appointment_date or r.created_at)

        # Zoek de meest recente afspraak (als die er is) voor afspraakdetails
        appointments = [r for r in records if r.intention_type == IntentionType.APPOINTMENT]
        detail_record = appointments[-1] if appointments else latest

        contact = ProcessedContact(
            email=email,
            first_name=_first_non_empty(records, "first_name"),
            last_name=_first_non_empty(records, "last_name"),
            phone=_first_non_empty(records, "phone"),
            event_name=event_name,
            salon_id=detail_record.salon_id,
            salon_name=detail_record.salon_name,
            stylist_id=detail_record.stylist_id,
            stylist_name=detail_record.stylist_name,
            treatment=detail_record.treatment,
            price=detail_record.price,
            appointment_date=detail_record.appointment_date,
            campaign_source=_first_non_empty(records, "campaign_source"),
            intention_count=intention_count,
            appointment_count=appointment_count,
        )
        contacts.append(contact)

        logger.info(
            f"Contact geaggregeerd: {email} → {event_name} "
            f"(intenties={intention_count}, afspraken={appointment_count})"
        )

    logger.info(f"Totaal geaggregeerd: {len(contacts)} unieke contacten uit {len(intentions)} records")
    return contacts


def _first_non_empty(records: list[BufferedIntention], field: str) -> str | None:
    """Geeft de eerste niet-lege waarde voor een veld uit een lijst records."""
    for record in reversed(records):  # Meest recent eerst
        value = getattr(record, field, None)
        if value:
            return value
    return None
