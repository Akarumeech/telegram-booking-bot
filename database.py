from datetime import date
from typing import Dict, List, Optional, Set

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    client_name TEXT    NOT NULL,
    phone       TEXT    NOT NULL,
    service     TEXT    NOT NULL,
    date        TEXT    NOT NULL,  -- YYYY-MM-DD
    time        TEXT    NOT NULL,  -- HH:MM
    status      TEXT    NOT NULL DEFAULT 'active',  -- active / cancelled
    reminded    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- на один слот может быть только одна активная запись,
-- даже если два клиента нажали «Подтвердить» одновременно
CREATE UNIQUE INDEX IF NOT EXISTS uniq_active_slot
    ON bookings(date, time) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS blocked_slots (
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    PRIMARY KEY (date, time)
);
"""


def _connect():
    return aiosqlite.connect(DB_PATH)


async def init_db() -> None:
    async with _connect() as conn:
        await conn.executescript(SCHEMA)
        await conn.commit()


async def get_taken_times(day: str) -> Set[str]:
    """Занятые и закрытые админом слоты на дату."""
    async with _connect() as conn:
        cur = await conn.execute(
            "SELECT time FROM bookings WHERE date = ? AND status = 'active' "
            "UNION SELECT time FROM blocked_slots WHERE date = ?",
            (day, day),
        )
        return {row[0] for row in await cur.fetchall()}


async def create_booking(
    user_id: int, client_name: str, phone: str, service: str,
    day: str, time: str, reminded: bool,
) -> Optional[int]:
    """Возвращает id записи или None, если слот уже заняли."""
    async with _connect() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM blocked_slots WHERE date = ? AND time = ?", (day, time)
        )
        if await cur.fetchone():
            return None
        try:
            cur = await conn.execute(
                "INSERT INTO bookings (user_id, client_name, phone, service, date, time, reminded) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, client_name, phone, service, day, time, int(reminded)),
            )
        except aiosqlite.IntegrityError:
            return None
        await conn.commit()
        return cur.lastrowid


async def get_booking(booking_id: int) -> Optional[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        return await cur.fetchone()


async def get_user_bookings(user_id: int) -> List[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM bookings WHERE user_id = ? AND status = 'active' AND date >= ? "
            "ORDER BY date, time",
            (user_id, date.today().isoformat()),
        )
        return list(await cur.fetchall())


async def cancel_booking(booking_id: int, user_id: Optional[int] = None) -> bool:
    """Отменяет запись. Если передан user_id — только свою."""
    query = "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status = 'active'"
    params = [booking_id]
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    async with _connect() as conn:
        cur = await conn.execute(query, params)
        await conn.commit()
        return cur.rowcount > 0


async def get_day_bookings(day: str) -> Dict[str, aiosqlite.Row]:
    """Активные записи на дату: {время: запись}."""
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM bookings WHERE date = ? AND status = 'active' ORDER BY time",
            (day,),
        )
        return {row["time"]: row for row in await cur.fetchall()}


async def get_blocked_times(day: str) -> Set[str]:
    async with _connect() as conn:
        cur = await conn.execute("SELECT time FROM blocked_slots WHERE date = ?", (day,))
        return {row[0] for row in await cur.fetchall()}


async def block_slot(day: str, time: str) -> None:
    async with _connect() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO blocked_slots (date, time) VALUES (?, ?)", (day, time)
        )
        await conn.commit()


async def unblock_slot(day: str, time: str) -> None:
    async with _connect() as conn:
        await conn.execute(
            "DELETE FROM blocked_slots WHERE date = ? AND time = ?", (day, time)
        )
        await conn.commit()


async def get_pending_reminders() -> List[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM bookings WHERE status = 'active' AND reminded = 0 AND date >= ?",
            (date.today().isoformat(),),
        )
        return list(await cur.fetchall())


async def mark_reminded(booking_id: int) -> None:
    async with _connect() as conn:
        await conn.execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,))
        await conn.commit()
