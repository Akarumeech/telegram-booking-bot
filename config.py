import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "bookings.db")

# Данные бизнеса — меняются под конкретного заказчика
BUSINESS_NAME = "Барбершоп «Бритва»"
CONTACTS = (
    "📍 ул. Пушкина, 10\n"
    "📞 +7 (900) 123-45-67\n"
    "🕙 Пн–Сб, 10:00–20:00"
)

# ключ: (название, цена в рублях)
SERVICES = {
    "haircut": ("Мужская стрижка", 1200),
    "beard": ("Оформление бороды", 800),
    "combo": ("Стрижка + борода", 1800),
    "kids": ("Детская стрижка", 900),
    "shave": ("Королевское бритьё", 1500),
}

WORK_START = 10          # первый слот, час
WORK_END = 20            # конец рабочего дня, час (последний слот — 19:00)
WORK_DAYS = {0, 1, 2, 3, 4, 5}  # 0 — понедельник, 6 — воскресенье
DAYS_AHEAD = 7           # на сколько дней вперёд можно записаться
REMIND_BEFORE_HOURS = 2  # за сколько часов напоминать о записи
