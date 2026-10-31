import html
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import database as db
import keyboards as kb
from config import ADMIN_ID, SERVICES
from utils import booking_summary, format_date

router = Router()
# все хендлеры этого роутера доступны только админу
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)


async def safe_edit(call: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def render_day(call: CallbackQuery, day: str) -> None:
    bookings = await db.get_day_bookings(day)
    blocked = await db.get_blocked_times(day)
    lines = [f"🗓 <b>Расписание на {format_date(day)}</b>\n"]
    if bookings:
        for time, b in bookings.items():
            lines.append(
                f"✅ <b>{time}</b> — {SERVICES[b['service']][0]}\n"
                f"     {html.escape(b['client_name'])}, {b['phone']}"
            )
    else:
        lines.append("Записей пока нет.")
    lines.append("\n<i>⚪ свободно — нажмите, чтобы закрыть слот\n"
                 "🔒 закрыто — нажмите, чтобы открыть\n"
                 "✅ запись — нажмите для подробностей</i>")
    await safe_edit(call, "\n".join(lines), kb.admin_day_kb(day, bookings, blocked))


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("🛠 <b>Панель администратора</b>", reply_markup=kb.admin_menu())


@router.callback_query(F.data == "adm:dates")
async def adm_dates(call: CallbackQuery):
    await safe_edit(
        call, "Выберите дату:", kb.dates_kb(prefix="adm:day", back="adm:menu")
    )
    await call.answer()


@router.callback_query(F.data == "adm:menu")
async def adm_menu(call: CallbackQuery):
    await safe_edit(call, "🛠 <b>Панель администратора</b>", kb.admin_menu())
    await call.answer()


@router.callback_query(F.data.startswith("adm:day:"))
async def adm_day(call: CallbackQuery):
    await render_day(call, call.data.split(":", 2)[2])
    await call.answer()


@router.callback_query(F.data.startswith("adm:slot:"))
async def adm_slot(call: CallbackQuery):
    _, _, day, time = call.data.split(":", 3)
    bookings = await db.get_day_bookings(day)
    if time in bookings:
        b = bookings[time]
        await safe_edit(
            call,
            f"📌 <b>Запись #{b['id']}</b>\n\n"
            + booking_summary(b["service"], day, time)
            + f"\n👤 {html.escape(b['client_name'])}\n📞 {b['phone']}",
            kb.admin_booking_kb(b["id"], day),
        )
        await call.answer()
        return
    if time in await db.get_blocked_times(day):
        await db.unblock_slot(day, time)
        await call.answer(f"Слот {time} открыт")
    else:
        await db.block_slot(day, time)
        await call.answer(f"Слот {time} закрыт")
    await render_day(call, day)


@router.callback_query(F.data.startswith("adm:cancel:"))
async def adm_cancel(call: CallbackQuery, bot: Bot):
    booking_id = int(call.data.split(":")[2])
    booking = await db.get_booking(booking_id)
    if not booking or not await db.cancel_booking(booking_id):
        await call.answer("Запись уже отменена", show_alert=True)
        return
    await call.answer("Запись отменена")
    try:
        await bot.send_message(
            booking["user_id"],
            "😔 К сожалению, ваша запись отменена администратором:\n\n"
            + booking_summary(booking["service"], booking["date"], booking["time"])
            + "\n\nВы можете выбрать другое время через «📅 Записаться».",
        )
    except Exception:
        logging.exception("Не удалось уведомить клиента об отмене")
    await render_day(call, booking["date"])
