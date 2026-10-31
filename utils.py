from datetime import date, datetime, timedelta
from typing import Iterable, List

from config import DAYS_AHEAD, SERVICES, WORK_DAYS, WORK_END, WORK_START

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def format_date(day: str) -> str:
    """'2026-11-03' -> 'вт, 03.11'"""
    d = date.fromisoformat(day)
    return f"{WEEKDAYS[d.weekday()]}, {d.strftime('%d.%m')}"


def booking_datetime(day: str, time: str) -> datetime:
    return datetime.strptime(f"{day} {time}", "%Y-%m-%d %H:%M")


def all_slots() -> List[str]:
    return [f"{h:02d}:00" for h in range(WORK_START, WORK_END)]


def working_dates() -> List[str]:
    today = date.today()
    days = (today + timedelta(days=i) for i in range(DAYS_AHEAD))
    return [d.isoformat() for d in days if d.weekday() in WORK_DAYS]


def free_slots(day: str, taken: Iterable[str]) -> List[str]:
    """Свободные слоты на дату без занятых и уже прошедших."""
    now = datetime.now()
    taken = set(taken)
    return [
        t for t in all_slots()
        if t not in taken and booking_datetime(day, t) > now
    ]


def booking_summary(service: str, day: str, time: str) -> str:
    name, price = SERVICES[service]
    return (
        f"💈 <b>{name}</b> — {price} ₽\n"
        f"📅 {format_date(day)} в {time}"
    )
