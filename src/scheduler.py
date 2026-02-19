"""Dagelijkse scheduler voor intentie-verwerking.

APScheduler cronjob die om middernacht draait:
1. Haalt onverwerkte intenties van gisteren op uit SQLite
2. Aggregeert per email via de processor
3. Stuurt naar Klaviyo
4. Markeert als verwerkt
"""

import logging
from datetime import date, timedelta

from src.database import get_unprocessed_intentions, mark_as_processed
from src.klaviyo_client import klaviyo_client
from src.processor import aggregate_intentions

logger = logging.getLogger(__name__)


async def run_daily_sync(target_date: date | None = None) -> dict:
    """Voer de dagelijkse sync uit.

    Args:
        target_date: Datum om te verwerken. Default: gisteren.

    Returns:
        Dict met resultaten van de sync.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    logger.info(f"Dagelijkse sync gestart voor {target_date}")

    # 1. Haal onverwerkte intenties op
    intentions = await get_unprocessed_intentions(target_date)

    if not intentions:
        logger.info(f"Geen onverwerkte intenties voor {target_date}")
        return {
            "date": target_date.isoformat(),
            "intentions_found": 0,
            "contacts_processed": 0,
            "success": 0,
            "failed": 0,
        }

    # 2. Aggregeer per email
    contacts = aggregate_intentions(intentions)

    # 3. Stuur naar Klaviyo
    success_count = 0
    failed_count = 0
    processed_ids: list[int] = []

    for contact in contacts:
        ok = await klaviyo_client.process_contact(contact)
        if ok:
            success_count += 1
        else:
            failed_count += 1

    # 4. Markeer alle intenties als verwerkt (ook bij Klaviyo fouten,
    #    zodat ze niet dubbel worden verwerkt)
    all_ids = [i.id for i in intentions if i.id is not None]
    await mark_as_processed(all_ids)

    result = {
        "date": target_date.isoformat(),
        "intentions_found": len(intentions),
        "contacts_processed": len(contacts),
        "success": success_count,
        "failed": failed_count,
    }

    logger.info(f"Dagelijkse sync voltooid: {result}")
    return result
