"""Klaviyo V3 API client.

Twee modi:
- SIMPLE:   Profile upsert (email + naam) + toevoegen aan lijst
            Scopes: profiles:write, lists:write
- EXTENDED: Profile upsert met custom properties + events
            Scopes: profiles:read/write, lists:read/write, events:write
"""

import logging
from datetime import datetime

import httpx

from src.config import AppMode, settings
from src.models import ProcessedContact

logger = logging.getLogger(__name__)

BASE_URL = "https://a.klaviyo.com/api"

# Retry configuratie
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconden


class KlaviyoClient:
    def __init__(self):
        self.api_key = settings.klaviyo_api_key
        self.list_id = settings.klaviyo_list_id
        self.revision = settings.klaviyo_api_revision
        self.mode = settings.mode

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Klaviyo-API-Key {self.api_key}",
            "Content-Type": "application/json",
            "revision": self.revision,
        }

    async def _request(self, method: str, url: str, json_data: dict | None = None) -> dict | None:
        """Voer een API request uit met exponential backoff retry."""
        import asyncio

        backoff = INITIAL_BACKOFF
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method, url, headers=self.headers, json=json_data
                    )

                    if response.status_code == 429:
                        retry_after = float(response.headers.get("Retry-After", backoff))
                        logger.warning(f"Rate limited, wacht {retry_after}s (poging {attempt}/{MAX_RETRIES})")
                        await asyncio.sleep(retry_after)
                        backoff *= 2
                        continue

                    response.raise_for_status()

                    if response.status_code == 204:
                        return None
                    return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(f"Klaviyo API fout: {e.response.status_code} - {e.response.text}")
                if attempt == MAX_RETRIES:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2

            except httpx.RequestError as e:
                logger.error(f"Klaviyo verbindingsfout: {e}")
                if attempt == MAX_RETRIES:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2

        return None

    async def upsert_profile(self, contact: ProcessedContact) -> str | None:
        """Maak of update een Klaviyo profiel. Geeft het profiel ID terug."""
        attributes: dict = {
            "email": contact.email,
        }
        if contact.first_name:
            attributes["first_name"] = contact.first_name
        if contact.last_name:
            attributes["last_name"] = contact.last_name
        if contact.phone:
            attributes["phone_number"] = contact.phone

        # Extended modus: voeg custom properties toe
        if self.mode == AppMode.EXTENDED:
            properties = {}
            if contact.salon_name:
                properties["salon_naam"] = contact.salon_name
            if contact.salon_id:
                properties["salon_id"] = contact.salon_id
            if contact.stylist_name:
                properties["kapper_naam"] = contact.stylist_name
            if contact.stylist_id:
                properties["stylist_id"] = contact.stylist_id
            if contact.is_new_client is not None:
                properties["is_nieuwe_klant"] = contact.is_new_client
            if contact.treatment:
                properties["laatste_behandeling"] = contact.treatment
            if contact.campaign_source:
                properties["campagne_bron"] = contact.campaign_source
            if properties:
                attributes["properties"] = properties

        payload = {
            "data": {
                "type": "profile",
                "attributes": attributes,
            }
        }

        result = await self._request("POST", f"{BASE_URL}/profile-import", json_data=payload)

        profile_id = None
        if result:
            profile_id = result.get("data", {}).get("id")
            logger.info(f"Profiel upserted: {contact.email} -> {profile_id}")

        return profile_id

    async def add_to_list(self, profile_id: str) -> None:
        """Voeg een profiel toe aan de geconfigureerde Klaviyo lijst."""
        if not self.list_id:
            logger.warning("Geen KLAVIYO_LIST_ID geconfigureerd, sla lijst-toevoeging over")
            return

        payload = {
            "data": [
                {
                    "type": "profile",
                    "id": profile_id,
                }
            ]
        }

        await self._request(
            "POST",
            f"{BASE_URL}/lists/{self.list_id}/relationships/profiles",
            json_data=payload,
        )
        logger.info(f"Profiel {profile_id} toegevoegd aan lijst {self.list_id}")

    async def create_event(self, contact: ProcessedContact) -> None:
        """Maak een Klaviyo event aan (alleen in extended modus)."""
        if self.mode != AppMode.EXTENDED:
            return

        properties = {
            "intention_count": contact.intention_count,
            "appointment_count": contact.appointment_count,
        }
        if contact.salon_name:
            properties["salon_naam"] = contact.salon_name
        if contact.salon_id:
            properties["salon_id"] = contact.salon_id
        if contact.stylist_name:
            properties["kapper_naam"] = contact.stylist_name
        if contact.stylist_id:
            properties["stylist_id"] = contact.stylist_id
        if contact.treatment:
            properties["behandeling"] = contact.treatment
        if contact.price is not None:
            properties["prijs"] = contact.price
        if contact.appointment_date:
            properties["afspraak_datum"] = contact.appointment_date.isoformat()
        if contact.campaign_source:
            properties["campagne_bron"] = contact.campaign_source

        payload = {
            "data": {
                "type": "event",
                "attributes": {
                    "metric": {
                        "data": {
                            "type": "metric",
                            "attributes": {
                                "name": contact.event_name,
                            }
                        }
                    },
                    "profile": {
                        "data": {
                            "type": "profile",
                            "attributes": {
                                "email": contact.email,
                            }
                        }
                    },
                    "properties": properties,
                    "time": datetime.utcnow().isoformat() + "Z",
                }
            }
        }

        await self._request("POST", f"{BASE_URL}/events", json_data=payload)
        logger.info(f"Event '{contact.event_name}' aangemaakt voor {contact.email}")

    async def process_contact(self, contact: ProcessedContact) -> bool:
        """Verwerk één contact volledig: profiel upsert + lijst + event."""
        try:
            profile_id = await self.upsert_profile(contact)
            if profile_id:
                await self.add_to_list(profile_id)
            await self.create_event(contact)
            return True
        except Exception as e:
            logger.error(f"Fout bij verwerken van {contact.email}: {e}")
            return False

    async def check_connection(self) -> dict:
        """Test de Klaviyo API verbinding. Gebruikt voor health check."""
        try:
            result = await self._request("GET", f"{BASE_URL}/lists")
            return {
                "status": "connected",
                "mode": self.mode.value,
                "list_id": self.list_id or "niet geconfigureerd",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "mode": self.mode.value,
            }


# Singleton instance
klaviyo_client = KlaviyoClient()
