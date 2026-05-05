import os
import logging
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import json

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
SHEET_NAME = os.getenv("SHEET_NAME", "Лист1")
REPORT_HOUR = int(os.getenv("REPORT_HOUR", "12"))
REPORT_MINUTE = int(os.getenv("REPORT_MINUTE", "0"))

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set!")
if not GROUP_CHAT_ID:
    raise RuntimeError("GROUP_CHAT_ID is not set!")
if not SPREADSHEET_ID:
    raise RuntimeError("SPREADSHEET_ID is not set!")

MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def get_sheet():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    creds_data = json.loads(creds_json)
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)


def get_today_report():
    today = datetime.now(MOSCOW_TZ)

    try:
        sheet = get_sheet()
        all_values = sheet.get_all_values()

        date_row = all_values[2] if len(all_values) > 2 else []
        headers = all_values[3] if len(all_values) > 3 else []
        values = all_values[5] if len(all_values) > 5 else []
        goods_rows = [r for r in all_values[8:] if any(r)]
        client_rows = [r for r in all_values[13:] if len(r) > 4 and any(r[4:])]

    except Exception as e:
        logger.error(f"Ошибка чтения таблицы: {e}")
        return f"Ошибка при чтении таблицы: {e}"

    date_display = date_row[0] if date_row else today.strftime("%d.%m.%Y")
    lines = [
        f"📊 *Ежедневный отчёт*",
        f"📅 *{date_display}*",
        "",
    ]

    EMOJI = ["📦", "💰", "📫", "🗃️", "💵", "🏦", "📈", "💸", "📉", "⚡"]
    for i, (h, v) in enumerate(zip(headers, values)):
        if h and v:
            em = EMOJI[i] if i < len(EMOJI) else "▪️"
            lines.append(f"{em} *{h}:* {v}")

    if goods_rows:
        lines.append("")
        lines.append("📋 *Список товара:*")
        for row in goods_rows:
            name = row[0] if len(row) > 0 else ""
            qty = row[1] if len(row) > 1 else ""
            if name:
                lines.append(f"  • {name}: {qty}")

    filled_clients = [r for r in client_rows if len(r) > 4 and r[4]]
    if filled_clients:
        lines.append("")
        lines.append("🧾 *По клиентам:*")
        for row in filled_clients:
            try:
                client = row[4] if len(row) > 4 else ""
                qty = row[5] if len(row) > 5 else ""
                storage = row[6] if len(row) > 6 else ""
                boxes = row[7] if len(row) > 7 else ""
                costs = row[8] if len(row) > 8 else ""
                revenue = row[9] if len(row) > 9 else ""
                margin = row[10] if len(row) > 10 else ""
                parts = [f"*{client}*"]
                if qty:
                    parts.append(f"кол-во: {qty}")
                if storage:
                    parts.append(f"склад: {storage}")
                if boxes:
                    parts.append(f"коробок: {boxes}")
                if costs:
                    parts.append(f"траты: {costs}")
                if revenue:
                    parts.append(f"выручка: {revenue}")
                if margin:
                    parts.append(f"маржа: {margin}")
                lines.append("  " + " | ".join(parts))
            except Exception:
                continue

    lines.append("")
    lines.append(f"🕐 Отправлено в {today.strftime('%H:%M')} МСК")
    return "\n".join(lines)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот ежедневных отчётов запущен!\n"
        "Команды:\n"
        "/report — отчёт прямо сейчас\n"
        "/chatid — узнать ID этого чата"
    )


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Загружаю данные из таблицы...")
    text = get_today_report()
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(f"Chat ID этого чата: `{cid}`", parse_mode="Markdown")


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


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
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
    logger.info(f"Бот запущен! Расписание: {REPORT_HOUR:02d}:{REPORT_MINUTE:02d} МСК")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
