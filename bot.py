import os
import logging
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import json

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Настройки ───────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
GROUP_CHAT_ID    = os.getenv("GROUP_CHAT_ID", "")
SPREADSHEET_ID   = os.getenv("SPREADSHEET_ID", "")
SHEET_NAME       = os.getenv("SHEET_NAME", "Лист1")
REPORT_HOUR      = int(os.getenv("REPORT_HOUR", "12"))
REPORT_MINUTE    = int(os.getenv("REPORT_MINUTE", "0"))

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set!")

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# ─── Google Sheets ────────────────────────────────────────────
def get_sheet():
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_data = json.loads(creds_json)
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)


def get_today_report() -> str:
    """Читает лист и возвращает отформатированное сообщение за сегодня."""
    today = datetime.now(MOSCOW_TZ)
    today_str = today.strftime("%-d-%b-%Y").replace(
        "Jan","янв").replace("Feb","фев").replace("Mar","мар").replace(
        "Apr","апр").replace("May","мая").replace("Jun","июн").replace(
        "Jul","июл").replace("Aug","авг").replace("Sep","сен").replace(
        "Oct","окт").replace("Nov","ноя").replace("Dec","дек")

    sheet = get_sheet()
    all_values = sheet.get_all_values()

    # Строка 3 (индекс 2) — дата; строка 4 (индекс 3) — заголовки; строка 6 (индекс 5) — значения
    # Структура из скриншота:
    # Row 1: "Ежедневный отчет" (заголовок)
    # Row 3: дата (например "3-мая-2026")
    # Row 4: заголовки столбцов
    # Row 6: значения

    try:
        date_cell = all_values[2][0] if len(all_values) > 2 else ""  # A3
        # Если дата не в A3 — ищем по всей строке 3
        date_row = all_values[2] if len(all_values) > 2 else []
        date_found = any(today.strftime("%d") in str(cell) for cell in date_row)

        headers = all_values[3] if len(all_values) > 3 else []   # строка 4
        values  = all_values[5] if len(all_values) > 5 else []   # строка 6

        # Данные товаров (строки 9+)
        goods_header = all_values[7] if len(all_values) > 7 else []   # строка 8
        goods_rows   = [r for r in all_values[8:] if any(r)]          # строки 9+

        # Клиенты (строки 13+, столбцы E-K)
        client_header = all_values[12] if len(all_values) > 12 else []  # строка 13
        client_rows   = [r for r in all_values[13:] if len(r) > 4 and any(r[4:])]

    except Exception as e:
        logger.error(f"Ошибка чтения таблицы: {e}")
        return f"❌ Ошибка при чтении таблицы: {e}"

    # ─── Формируем сообщение ─────────────────────────────────
    date_display = date_row[0] if date_row else today.strftime("%d.%m.%Y")
    lines = [
        f"📊 *Ежедневный отчёт*",
        f"📅 *{date_display}*",
        "",
    ]

    # Основные показатели
    EMOJI = ["📦","💰","📫","🗃️","💵","🏦","📈","💸","📉","⚡"]
    for i, (h, v) in enumerate(zip(headers, values)):
        if h and v:
            em = EMOJI[i] if i < len(EMOJI) else "▪️"
            lines.append(f"{em} *{h}:* {v}")

    # Список товаров
    if goods_rows:
        lines.append("")
        lines.append("📋 *Список товара:*")
        for row in goods_rows:
            name = row[0] if len(row) > 0 else ""
            qty  = row[1] if len(row) > 1 else ""
            if name:
                lines.append(f"  • {name}: {qty}")

    # Клиенты
    filled_clients = [r for r in client_rows if len(r) > 4 and r[4]]
    if filled_clients:
        lines.append("")
        lines.append("🧾 *По клиентам:*")
        for row in filled_clients:
            try:
                client  = row[4]  if len(row) > 4  else ""
                qty     = row[5]  if len(row) > 5  else ""
                storage = row[6]  if len(row) > 6  else ""
                boxes   = row[7]  if len(row) > 7  else ""
                costs   = row[8]  if len(row) > 8  else ""
                revenue = row[9]  if len(row) > 9  else ""
                margin  = row[10] if len(row) > 10 else ""
                parts = [f"*{client}*"]
                if qty:     parts.append(f"кол-во: {qty}")
                if storage: parts.append(f"склад: {storage}")
                if boxes:   parts.append(f"коробок: {boxes}")
                if costs:   parts.append(f"траты: {costs}")
                if revenue: parts.append(f"выручка: {revenue}")
                if margin:  parts.append(f"маржа: {margin}")
                lines.append("  " + " | ".join(parts))
            except Exception:
                continue

    lines.append("")
    lines.append(f"🕐 Отправлено в {today.strftime('%H:%M')} МСК")
    return "\n".join(lines)


# ─── Команды бота ─────────────────────────────────────────────
async def cmd_start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот ежедневных отчётов запущен!\n"
        "Команды:\n"
        "/report — отчёт прямо сейчас\n"
        "/chatid — узнать ID этого чата"
    )

async def cmd_report(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Загружаю данные из таблицы...")
    text = get_today_report()
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_chatid(update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(f"Chat ID этого чата: `{cid}`", parse_mode="Markdown")


# ─── Авторасписание ───────────────────────────────────────────
async def send_daily_report(bot: Bot):
    logger.info("Отправляю ежедневный отчёт...")
    try:
        text = get_today_report()
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info("Отчёт успешно отправлен.")
    except Exception as e:
        logger.error(f"Ошибка отправки отчёта: {e}")


# ─── Запуск ───────────────────────────────────────────────────
def main():
   app = Application.builder().token(TELEGRAM_TOKEN).arbitrary_callback_data(False).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("chatid", cmd_chatid))

    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    scheduler.add_job(
        send_daily_report,
        trigger="cron",
        hour=REPORT_HOUR,
        minute=REPORT_MINUTE,
        args=[app.bot],
    )
    scheduler.start()
    logger.info(f"Расписание: каждый день в {REPORT_HOUR:02d}:{REPORT_MINUTE:02d} МСК")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
