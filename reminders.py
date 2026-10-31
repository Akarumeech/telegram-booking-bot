import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot

import database as db
from config import BUSINESS_NAME, CONTACTS, REMIND_BEFORE_HOURS
from utils import booking_datetime, booking_summary

CHECK_INTERVAL = 60  # секунд


async def send_reminders(bot: Bot) -> None:
    now = datetime.now()
    window = now + timedelta(hours=REMIND_BEFORE_HOURS)
    for b in await db.get_pending_reminders():
        if not now < booking_datetime(b["date"], b["time"]) <= window:
            continue
        try:
            await bot.send_message(
                b["user_id"],
                f"⏰ <b>Напоминание</b>\n\nСкоро ваш визит в {BUSINESS_NAME}:\n\n"
                + booking_summary(b["service"], b["date"], b["time"])
                + f"\n\n{CONTACTS}",
            )
        except Exception:
            # клиент мог заблокировать бота — помечаем, чтобы не пытаться снова
            logging.exception("Не удалось отправить напоминание по записи #%s", b["id"])
        await db.mark_reminded(b["id"])


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            await send_reminders(bot)
        except Exception:
            logging.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(CHECK_INTERVAL)
