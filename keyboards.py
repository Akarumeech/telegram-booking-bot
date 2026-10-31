from typing import Dict, List, Set

from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import SERVICES
from utils import all_slots, format_date, working_dates

BTN_BOOK = "📅 Записаться"
BTN_MY = "🗂 Мои записи"
BTN_PRICES = "💈 Услуги и цены"
BTN_CONTACTS = "📍 Контакты"
BTN_CANCEL = "❌ Отмена"


# ---------- Reply-клавиатуры ----------

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BOOK)],
            [KeyboardButton(text=BTN_MY), KeyboardButton(text=BTN_PRICES)],
            [KeyboardButton(text=BTN_CONTACTS)],
        ],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


# ---------- Inline: запись клиента ----------

def services_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, (name, price) in SERVICES.items():
        b.button(text=f"{name} — {price} ₽", callback_data=f"svc:{key}")
    b.button(text="✖️ Отменить", callback_data="flow:cancel")
    b.adjust(1)
    return b.as_markup()


def dates_kb(prefix: str = "date", back: str = "back:services") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for day in working_dates():
        b.button(text=format_date(day), callback_data=f"{prefix}:{day}")
    b.adjust(2)
    b.row(*InlineKeyboardBuilder().button(text="⬅️ Назад", callback_data=back).buttons)
    return b.as_markup()


def times_kb(times: List[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in times:
        b.button(text=t, callback_data=f"time:{t}")
    b.adjust(3)
    b.row(*InlineKeyboardBuilder().button(text="⬅️ Назад", callback_data="back:dates").buttons)
    return b.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data="flow:confirm")
    b.button(text="✖️ Отменить", callback_data="flow:cancel")
    b.adjust(2)
    return b.as_markup()


def my_bookings_kb(bookings) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for row in bookings:
        b.button(
            text=f"❌ Отменить {format_date(row['date'])} {row['time']}",
            callback_data=f"ucancel:{row['id']}",
        )
    b.adjust(1)
    return b.as_markup()


# ---------- Inline: админка ----------

def admin_menu() -> InlineKeyboardMarkup:
    dates = working_dates()
    b = InlineKeyboardBuilder()
    if dates:
        b.button(text=f"📋 {format_date(dates[0])}", callback_data=f"adm:day:{dates[0]}")
    if len(dates) > 1:
        b.button(text=f"📋 {format_date(dates[1])}", callback_data=f"adm:day:{dates[1]}")
    b.button(text="📆 Другая дата", callback_data="adm:dates")
    b.adjust(2, 1)
    return b.as_markup()


def admin_day_kb(day: str, bookings: Dict[str, object], blocked: Set[str]) -> InlineKeyboardMarkup:
    """Сетка слотов: ✅ — запись, 🔒 — закрыт, ⚪ — свободен."""
    b = InlineKeyboardBuilder()
    for t in all_slots():
        if t in bookings:
            icon = "✅"
        elif t in blocked:
            icon = "🔒"
        else:
            icon = "⚪"
        b.button(text=f"{icon} {t}", callback_data=f"adm:slot:{day}:{t}")
    b.adjust(3)
    b.row(*InlineKeyboardBuilder().button(text="⬅️ К датам", callback_data="adm:dates").buttons)
    return b.as_markup()


def admin_booking_kb(booking_id: int, day: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отменить запись", callback_data=f"adm:cancel:{booking_id}")
    b.button(text="⬅️ Назад", callback_data=f"adm:day:{day}")
    b.adjust(1)
    return b.as_markup()
