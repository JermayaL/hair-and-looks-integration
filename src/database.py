"""SQLite buffer voor Salonhub intenties/afspraken.

Slaat binnenkomende webhook data tijdelijk op.
De dagelijkse scheduler haalt onverwerkte records op,
de processor aggregeert ze, en markeert ze als verwerkt.
"""

import json
import logging
from datetime import date, datetime

import aiosqlite

from src.config import settings
from src.models import BufferedIntention, IntentionType

logger = logging.getLogger(__name__)

DB_PATH = str(settings.db_path)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS intentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    phone TEXT,
    intention_type TEXT NOT NULL,
    salon_id TEXT,
    salon_name TEXT,
    stylist_id TEXT,
    stylist_name TEXT,
    treatment TEXT,
    price REAL,
    appointment_date TEXT,
    campaign_source TEXT,
    raw_payload TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_intentions_email ON intentions(email);
CREATE INDEX IF NOT EXISTS idx_intentions_processed ON intentions(processed);
CREATE INDEX IF NOT EXISTS idx_intentions_created_at ON intentions(created_at);
"""


async def init_db() -> None:
    """Maak de database en tabel aan als die niet bestaan."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLE_SQL)
        await db.commit()
    logger.info(f"Database geïnitialiseerd: {DB_PATH}")


async def save_intention(intention: BufferedIntention) -> int:
    """Sla een intentie/afspraak op in de buffer. Geeft het ID terug."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO intentions
                (email, first_name, last_name, phone, intention_type,
                 salon_id, salon_name, stylist_id, stylist_name,
                 treatment, price, appointment_date, campaign_source, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intention.email,
                intention.first_name,
                intention.last_name,
                intention.phone,
                intention.intention_type.value,
                intention.salon_id,
                intention.salon_name,
                intention.stylist_id,
                intention.stylist_name,
                intention.treatment,
                intention.price,
                intention.appointment_date.isoformat() if intention.appointment_date else None,
                intention.campaign_source,
                intention.raw_payload,
            ),
        )
        await db.commit()
        row_id = cursor.lastrowid
        logger.info(f"Intentie opgeslagen: id={row_id}, email={intention.email}, type={intention.intention_type.value}")
        return row_id


async def get_unprocessed_intentions(target_date: date | None = None) -> list[BufferedIntention]:
    """Haal alle onverwerkte intenties op, optioneel gefilterd op datum."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if target_date:
            date_str = target_date.isoformat()
            cursor = await db.execute(
                """
                SELECT * FROM intentions
                WHERE processed = 0 AND date(created_at) = ?
                ORDER BY created_at ASC
                """,
                (date_str,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM intentions WHERE processed = 0 ORDER BY created_at ASC"
            )
        rows = await cursor.fetchall()

    intentions = []
    for row in rows:
        intentions.append(
            BufferedIntention(
                id=row["id"],
                email=row["email"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                phone=row["phone"],
                intention_type=IntentionType(row["intention_type"]),
                salon_id=row["salon_id"],
                salon_name=row["salon_name"],
                stylist_id=row["stylist_id"],
                stylist_name=row["stylist_name"],
                treatment=row["treatment"],
                price=row["price"],
                appointment_date=datetime.fromisoformat(row["appointment_date"]) if row["appointment_date"] else None,
                campaign_source=row["campaign_source"],
                raw_payload=row["raw_payload"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                processed=bool(row["processed"]),
            )
        )

    logger.info(f"Onverwerkte intenties opgehaald: {len(intentions)} records")
    return intentions


async def mark_as_processed(intention_ids: list[int]) -> None:
    """Markeer intenties als verwerkt."""
    if not intention_ids:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        placeholders = ",".join("?" for _ in intention_ids)
        await db.execute(
            f"UPDATE intentions SET processed = 1 WHERE id IN ({placeholders})",
            intention_ids,
        )
        await db.commit()
    logger.info(f"Intenties gemarkeerd als verwerkt: {len(intention_ids)} records")


async def get_intention_count() -> dict:
    """Geeft tellingen terug voor monitoring."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM intentions WHERE processed = 0")
        row = await cursor.fetchone()
        unprocessed = row[0] if row else 0

        cursor = await db.execute("SELECT COUNT(*) FROM intentions")
        row = await cursor.fetchone()
        total = row[0] if row else 0

    return {"total": total, "unprocessed": unprocessed, "processed": total - unprocessed}
