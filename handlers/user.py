import html
import logging
import re
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from config import ADMIN_ID, BUSINESS_NAME, CONTACTS, REMIND_BEFORE_HOURS, SERVICES
from utils import booking_datetime, booking_summary, format_date, free_slots

router = Router()

PHONE_RE = re.compile(r"^\+?\d{10,15}$")


class Booking(StatesGroup):
    service = State()
    date = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


async def notify_admin(bot: Bot, text: str) -> None:
    if not ADMIN_ID:
        return
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        logging.exception("Не удалось отправить уведомление админу")


# ---------- Главное меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {html.escape(message.from_user.first_name)}! 👋\n"
        f"Это бот записи в <b>{BUSINESS_NAME}</b>.\n\n"
        "Выберите, что вас интересует:",
        reply_markup=kb.main_menu(),
    )


@router.message(F.text == kb.BTN_CANCEL)
async def cancel_text(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Запись отменена.", reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_PRICES)
async def show_prices(message: Message):
    lines = [f"• {name} — <b>{price} ₽</b>" for name, price in SERVICES.values()]
    await message.answer("💈 <b>Услуги и цены</b>\n\n" + "\n".join(lines))


@router.message(F.text == kb.BTN_CONTACTS)
async def show_contacts(message: Message):
    await message.answer(f"<b>{BUSINESS_NAME}</b>\n\n{CONTACTS}")


@router.message(F.text == kb.BTN_MY)
async def my_bookings(message: Message, state: FSMContext):
    await state.clear()
    bookings = await db.get_user_bookings(message.from_user.id)
    if not bookings:
        await message.answer("У вас нет предстоящих записей.", reply_markup=kb.main_menu())
        return
    text = "🗂 <b>Ваши записи</b>\n\n" + "\n\n".join(
        booking_summary(b["service"], b["date"], b["time"]) for b in bookings
    )
    await message.answer(text, reply_markup=kb.my_bookings_kb(bookings))


@router.callback_query(F.data.startswith("ucancel:"))
async def user_cancel(call: CallbackQuery, bot: Bot):
    booking_id = int(call.data.split(":")[1])
    booking = await db.get_booking(booking_id)
    if not booking or not await db.cancel_booking(booking_id, call.from_user.id):
        await call.answer("Запись уже отменена", show_alert=True)
        return
    await call.message.edit_text(
        "Запись отменена ❌\n\n" + booking_summary(booking["service"], booking["date"], booking["time"])
    )
    await call.answer()
    await notify_admin(
        bot,
        "❌ <b>Клиент отменил запись</b>\n\n"
        + booking_summary(booking["service"], booking["date"], booking["time"])
        + f"\n👤 {html.escape(booking['client_name'])}, {booking['phone']}",
    )


# ---------- Запись: услуга → дата → время → имя → телефон → подтверждение ----------

@router.message(F.text == kb.BTN_BOOK)
async def start_booking(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Booking.service)
    await message.answer("Выберите услугу:", reply_markup=kb.services_kb())


@router.callback_query(F.data == "flow:cancel")
async def cancel_flow(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Запись отменена.")
    await call.message.answer("Главное меню:", reply_markup=kb.main_menu())
    await call.answer()


@router.callback_query(Booking.service, F.data.startswith("svc:"))
async def choose_service(call: CallbackQuery, state: FSMContext):
    service = call.data.split(":")[1]
    if service not in SERVICES:
        await call.answer("Услуга не найдена", show_alert=True)
        return
    await state.update_data(service=service)
    await state.set_state(Booking.date)
    await call.message.edit_text(
        f"Услуга: <b>{SERVICES[service][0]}</b>\n\nВыберите дату:",
        reply_markup=kb.dates_kb(),
    )
    await call.answer()


@router.callback_query(Booking.date, F.data == "back:services")
async def back_to_services(call: CallbackQuery, state: FSMContext):
    await state.set_state(Booking.service)
    await call.message.edit_text("Выберите услугу:", reply_markup=kb.services_kb())
    await call.answer()


async def show_times(call: CallbackQuery, state: FSMContext, day: str, alert: str = "") -> None:
    data = await state.get_data()
    times = free_slots(day, await db.get_taken_times(day))
    if not times:
        if alert:
            # пока клиент выбирал, разобрали последние слоты — возвращаем к датам
            await state.set_state(Booking.date)
            await call.message.edit_text(
                f"Услуга: <b>{SERVICES[data['service']][0]}</b>\n\nВыберите дату:",
                reply_markup=kb.dates_kb(),
            )
        await call.answer("На эту дату свободного времени нет 😔", show_alert=True)
        return
    await state.update_data(date=day)
    await state.set_state(Booking.time)
    await call.message.edit_text(
        f"Услуга: <b>{SERVICES[data['service']][0]}</b>\n"
        f"Дата: <b>{format_date(day)}</b>\n\nВыберите время:",
        reply_markup=kb.times_kb(times),
    )
    await call.answer(alert, show_alert=bool(alert))


@router.callback_query(Booking.date, F.data.startswith("date:"))
async def choose_date(call: CallbackQuery, state: FSMContext):
    await show_times(call, state, call.data.split(":", 1)[1])


@router.callback_query(Booking.time, F.data == "back:dates")
async def back_to_dates(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(Booking.date)
    await call.message.edit_text(
        f"Услуга: <b>{SERVICES[data['service']][0]}</b>\n\nВыберите дату:",
        reply_markup=kb.dates_kb(),
    )
    await call.answer()


@router.callback_query(Booking.time, F.data.startswith("time:"))
async def choose_time(call: CallbackQuery, state: FSMContext):
    time = call.data.split(":", 1)[1]
    data = await state.get_data()
    if time not in free_slots(data["date"], await db.get_taken_times(data["date"])):
        await show_times(call, state, data["date"], alert="Это время только что заняли, выберите другое")
        return
    await state.update_data(time=time)
    await state.set_state(Booking.name)
    await call.message.edit_text(booking_summary(data["service"], data["date"], time))
    await call.message.answer("Как к вам обращаться?", reply_markup=kb.cancel_kb())
    await call.answer()


@router.message(Booking.name, F.text)
async def enter_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not 2 <= len(name) <= 50:
        await message.answer("Введите имя от 2 до 50 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(Booking.phone)
    await message.answer(
        "Отправьте номер телефона кнопкой ниже или введите вручную:",
        reply_markup=kb.phone_kb(),
    )


@router.message(Booking.phone, F.contact | F.text)
async def enter_phone(message: Message, state: FSMContext):
    raw = message.contact.phone_number if message.contact else message.text
    phone = re.sub(r"[\s\-()]", "", raw)
    if not PHONE_RE.match(phone):
        await message.answer("Не похоже на номер телефона. Пример: +79001234567")
        return
    if len(phone) == 11 and phone.startswith("8"):
        phone = "7" + phone[1:]  # 8 900 ... -> +7 900 ...
    if not phone.startswith("+"):
        phone = "+" + phone
    await state.update_data(phone=phone)
    await state.set_state(Booking.confirm)
    data = await state.get_data()
    await message.answer("Почти готово!", reply_markup=kb.main_menu())
    await message.answer(
        "Проверьте данные:\n\n"
        + booking_summary(data["service"], data["date"], data["time"])
        + f"\n👤 {html.escape(data['name'])}\n📞 {phone}",
        reply_markup=kb.confirm_kb(),
    )


@router.callback_query(Booking.confirm, F.data == "flow:confirm")
async def confirm_booking(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    starts_at = booking_datetime(data["date"], data["time"])
    # если до визита меньше REMIND_BEFORE_HOURS, отдельное напоминание не нужно
    soon = starts_at - datetime.now() <= timedelta(hours=REMIND_BEFORE_HOURS)
    booking_id = await db.create_booking(
        call.from_user.id, data["name"], data["phone"], data["service"],
        data["date"], data["time"], reminded=soon,
    )
    if booking_id is None:
        await state.set_state(Booking.date)
        await call.message.edit_text(
            "😔 Это время уже заняли. Выберите другую дату или время:",
            reply_markup=kb.dates_kb(),
        )
        await call.answer()
        return

    await state.clear()
    summary = booking_summary(data["service"], data["date"], data["time"])
    await call.message.edit_text(
        f"✅ <b>Вы записаны!</b>\n\n{summary}\n\n"
        f"Напомним за {REMIND_BEFORE_HOURS} ч до визита. "
        "Отменить запись можно в разделе «Мои записи»."
    )
    await call.answer("Готово!")
    await notify_admin(
        bot,
        f"🆕 <b>Новая запись #{booking_id}</b>\n\n{summary}\n"
        f"👤 {html.escape(data['name'])}, {data['phone']}",
    )


@router.callback_query(F.data.startswith(("svc:", "date:", "time:", "back:", "flow:")))
async def stale_button(call: CallbackQuery):
    # кнопки из старого сообщения после перезапуска бота или завершённой записи
    await call.answer("Эта кнопка устарела. Начните запись заново.", show_alert=True)
