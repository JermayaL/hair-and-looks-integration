"""Salonhub webhook ontvanger.

POST /webhook/salonhub — ontvangt afspraakdata van Salonhub.
Valideert HMAC signature, parst de payload, en slaat op in SQLite buffer.
"""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from src.config import settings
from src.database import save_intention
from src.models import (
    BufferedIntention,
    IntentionType,
    SalonhubWebhookPayload,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_signature(payload_body: bytes, signature: str | None) -> bool:
    """Verifieer de HMAC-SHA256 signature van de webhook."""
    if not settings.webhook_secret:
        logger.warning("WEBHOOK_SECRET niet geconfigureerd, sla signature verificatie over")
        return True

    if not signature:
        return False

    expected = hmac.new(
        settings.webhook_secret.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/webhook/salonhub")
async def receive_salonhub_webhook(
    request: Request,
    x_webhook_signature: str | None = Header(None, alias="X-Webhook-Signature"),
):
    """Ontvang en buffer een Salonhub webhook.

    TODO: Het exacte header-naam voor de signature en het payload formaat
    moeten worden aangepast zodra Salonhub documentatie beschikbaar is.
    """
    raw_body = await request.body()

    # Signature verificatie
    if not verify_signature(raw_body, x_webhook_signature):
        logger.warning("Ongeldige webhook signature ontvangen")
        raise HTTPException(status_code=401, detail="Ongeldige signature")

    # Parse de payload
    try:
        raw_json = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ongeldige JSON")

    # Probeer te parsen met ons model, maar sla altijd de raw data op
    try:
        payload = SalonhubWebhookPayload.model_validate(raw_json)
    except Exception:
        # Onbekend formaat — sla raw op voor latere verwerking
        logger.warning("Webhook payload matcht niet verwacht formaat, sla raw op")
        payload = SalonhubWebhookPayload(raw_data=raw_json)

    # Bepaal het type intentie
    # TODO: Aanpassen aan werkelijke Salonhub event types
    intention_type = IntentionType.INTENTION
    if payload.event_type and "appointment" in payload.event_type.lower():
        if "cancel" not in payload.event_type.lower():
            intention_type = IntentionType.APPOINTMENT

    # Extraheer email — vereist voor verwerking
    email = None
    if payload.customer and payload.customer.email:
        email = payload.customer.email

    if not email:
        # Probeer email uit raw data te halen
        # TODO: Pad aanpassen aan werkelijk Salonhub formaat
        email = _extract_email_from_raw(raw_json)

    if not email:
        logger.info("Webhook ontvangen zonder email, genegeerd")
        return {"status": "ignored", "reason": "no_email"}

    # Bouw het intentie-record
    intention = BufferedIntention(
        email=email,
        first_name=payload.customer.first_name if payload.customer else None,
        last_name=payload.customer.last_name if payload.customer else None,
        phone=payload.customer.phone if payload.customer else None,
        intention_type=intention_type,
        salon_id=payload.appointment.salon_id if payload.appointment else None,
        salon_name=payload.appointment.salon_name if payload.appointment else None,
        stylist_id=payload.appointment.stylist_id if payload.appointment else None,
        stylist_name=payload.appointment.stylist_name if payload.appointment else None,
        treatment=payload.appointment.treatment if payload.appointment else None,
        price=payload.appointment.price if payload.appointment else None,
        appointment_date=payload.appointment.date if payload.appointment else None,
        raw_payload=json.dumps(raw_json, default=str),
    )

    record_id = await save_intention(intention)

    logger.info(f"Webhook verwerkt: id={record_id}, email={email}, type={intention_type.value}")

    return {
        "status": "buffered",
        "id": record_id,
        "type": intention_type.value,
    }


def _extract_email_from_raw(data: dict) -> str | None:
    """Probeer een email te vinden in een onbekend JSON formaat.

    Doorzoekt veelvoorkomende veldnamen recursief.
    TODO: Aanpassen/verwijderen zodra Salonhub formaat bekend is.
    """
    email_keys = {"email", "e-mail", "emailAddress", "email_address", "customerEmail"}

    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower().replace("-", "").replace("_", "") in {k.lower().replace("-", "").replace("_", "") for k in email_keys}:
                if isinstance(value, str) and "@" in value:
                    return value
            if isinstance(value, dict):
                result = _extract_email_from_raw(value)
                if result:
                    return result
    return None
