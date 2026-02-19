"""Pydantic models voor Salonhub webhook payloads en Klaviyo API.

LET OP: Het Salonhub webhook formaat is nog niet definitief.
Zodra Salonhub de webhook documentatie deelt, pas de
SalonhubWebhookPayload en veldmapping hieronder aan.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Salonhub inkomende webhook payload
# ---------------------------------------------------------------------------
# TODO: Aanpassen zodra Salonhub webhook documentatie beschikbaar is.
# Huidige structuur is een educated guess op basis van typische salon-software.

class SalonhubEventType(str, Enum):
    APPOINTMENT_CREATED = "appointment.created"
    APPOINTMENT_UPDATED = "appointment.updated"
    APPOINTMENT_CANCELLED = "appointment.cancelled"
    INTENTION = "intention"  # Klant start boekingsproces maar rondt niet af


class SalonhubCustomer(BaseModel):
    """Klantgegevens uit Salonhub webhook."""
    email: EmailStr | None = None
    first_name: str | None = Field(None, alias="firstName")
    last_name: str | None = Field(None, alias="lastName")
    phone: str | None = None

    model_config = {"populate_by_name": True}


class SalonhubAppointment(BaseModel):
    """Afspraakgegevens uit Salonhub webhook."""
    # TODO: Velden aanpassen aan werkelijk Salonhub formaat
    appointment_id: str | None = Field(None, alias="appointmentId")
    salon_id: str | None = Field(None, alias="salonId")
    salon_name: str | None = Field(None, alias="salonName")
    stylist_id: str | None = Field(None, alias="stylistId")
    stylist_name: str | None = Field(None, alias="stylistName")
    treatment: str | None = None
    price: float | None = None
    date: datetime | None = None

    model_config = {"populate_by_name": True}


class SalonhubWebhookPayload(BaseModel):
    """Volledige Salonhub webhook payload.

    TODO: Dit model aanpassen zodra de werkelijke Salonhub
    webhook structuur bekend is. De velden hieronder zijn
    een flexibele basis.
    """
    event_type: str | None = Field(None, alias="eventType")
    customer: SalonhubCustomer | None = None
    appointment: SalonhubAppointment | None = None
    timestamp: datetime | None = None

    # Vangnet: sla de volledige raw payload ook op
    raw_data: dict | None = Field(None, alias="rawData")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Interne intentie-representatie (opgeslagen in SQLite buffer)
# ---------------------------------------------------------------------------

class IntentionType(str, Enum):
    INTENTION = "intention"
    APPOINTMENT = "appointment"


class BufferedIntention(BaseModel):
    """Eén intentie/afspraak record in de SQLite buffer."""
    id: int | None = None
    email: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    intention_type: IntentionType
    salon_id: str | None = None
    salon_name: str | None = None
    stylist_id: str | None = None
    stylist_name: str | None = None
    treatment: str | None = None
    price: float | None = None
    appointment_date: datetime | None = None
    campaign_source: str | None = None
    raw_payload: str | None = None
    created_at: datetime | None = None
    processed: bool = False


# ---------------------------------------------------------------------------
# Klaviyo API models (V3)
# ---------------------------------------------------------------------------

class KlaviyoProfileAttributes(BaseModel):
    """Klaviyo profile attributes voor upsert."""
    email: str
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    properties: dict | None = None


class KlaviyoProfileUpsert(BaseModel):
    """Klaviyo V3 profile upsert request body."""
    type: str = "profile"
    attributes: KlaviyoProfileAttributes


class KlaviyoEventAttributes(BaseModel):
    """Klaviyo V3 event create attributes."""
    metric: dict  # {"data": {"type": "metric", "attributes": {"name": "..."}}}
    profile: dict  # {"data": {"type": "profile", "attributes": {"email": "..."}}}
    properties: dict | None = None
    time: str | None = None


class KlaviyoEvent(BaseModel):
    """Klaviyo V3 event create request body."""
    type: str = "event"
    attributes: KlaviyoEventAttributes


# ---------------------------------------------------------------------------
# Verwerkt resultaat na dagelijkse aggregatie
# ---------------------------------------------------------------------------

class ProcessedContact(BaseModel):
    """Resultaat van processor: één contact klaar voor Klaviyo."""
    email: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    event_name: str  # "appointmentMade" of "appointmentIntention"
    salon_id: str | None = None
    salon_name: str | None = None
    stylist_id: str | None = None
    stylist_name: str | None = None
    treatment: str | None = None
    price: float | None = None
    appointment_date: datetime | None = None
    campaign_source: str | None = None
    is_new_client: bool | None = None
    intention_count: int = 0
    appointment_count: int = 0
