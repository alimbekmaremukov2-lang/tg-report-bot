import os
import logging
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
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


def get_client():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    creds_data = json.loads(creds_json)
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    return gspread.authorize(creds)


def get_today_report():
    today = datetime.now(MOSCOW_TZ)
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet(SHEET_NAME)
        all_values = sheet.get_all_values()

        # Строка 3 — дата
        date_row = all_values[2] if len(all_values) > 2 else []
        # Строка 4 — заголовки (A4:P4)
        headers = all_values[3] if len(all_values) > 3 else []
        # Строка 6 — значения (A6:P6)
        values = all_values[5] if len(all_values) > 5 else []
        # Строки 9-10 — список товара
        goods_rows = [r for r in all_values[8:12] if r[0].strip() and r[0].strip() not in ("Список товара",)]
        # Строки 14+ — клиенты
        client_rows = [r for r in all_values[13:] if len(r) > 4 and r[4].strip()]

        # Читаем примечание к ячейке P6 (продуктивность по сотрудникам)
        productivity_note = ""
        try:
            cell = sheet.cell(6, 16)  # строка 6, столбец P (16)
            if cell.note:
                productivity_note = cell.note.strip()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Ошибка чтения таблицы: {e}")
        return f"Ошибка при чтении таблицы: {e}"

    date_display = date_row[0] if date_row else today.strftime("%d.%m.%Y")

    lines = [
        "📊 *Ежедневный отчёт*",
        f"📅 {date_display}",
        "──────────────────────",
    ]

    # Заголовки и значения — столбцы A-P (индексы 0-15)
    # Специальный порядок: после кол-ва товара (A) вставляем список товара
    for i, (h, v) in enumerate(zip(headers, values)):
        if not h.strip() or not v.strip():
            continue

        lines.append(f"\n*{h.strip()}*")
        lines.append(v.strip())

        # После "Кол-во обработанного товара" (столбец A, индекс 0) — список товара
        if i == 0 and goods_rows:
            lines.append("📋 *Список товара:*")
            for row in goods_rows:
                name = row[0].strip() if len(row) > 0 else ""
                qty = row[1].strip() if len(row) > 1 else ""
                if name:
                    lines.append(f"• {name}: {qty}")

        # После "Продуктивность команды" (последний столбец P, индекс 15) — примечание
        if i == 15 and productivity_note:
            lines.append("──────────────────────")
            for note_line in productivity_note.split("\n"):
                if note_line.strip():
                    lines.append(note_line.strip())

    # Доставка
    if client_rows:
        lines.append("\n──────────────────────")
        lines.append("🚚 *Доставка:*")
        for row in client_rows:
            try:
                client_name = row[4].strip() if len(row) > 4 else ""
                qty = row[5].strip() if len(row) > 5 else ""
                storage = row[6].strip() if len(row) > 6 else ""
                boxes = row[7].strip() if len(row) > 7 else ""
                costs = row[8].strip() if len(row) > 8 else ""
                revenue = row[9].strip() if len(row) > 9 else ""
                margin = row[10].strip() if len(row) > 10 else ""
                if not client_name:
                    continue
                parts = [f"*{client_name}*"]
                if qty:
                    parts.append(f"{qty} шт")
                if storage:
                    parts.append(storage)
                if boxes:
                    parts.append(f"{boxes} кор")
                if costs:
                    parts.append(f"{costs} р")
                if revenue:
                    parts.append(revenue)
                if margin:
                    parts.append(margin)
                lines.append(" | ".join(parts))
            except Exception:
                continue

    lines.append("\n──────────────────────")
    lines.append(f"🕐 {today.strftime('%H:%M')} МСК")
    return "\n".join(lines)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот ежедневных отчётов запущен!\n"
        "/report — отчёт прямо сейчас\n"
        "/chatid — узнать ID этого чата"
    )


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Загружаю данные...")
    text = get_today_report()
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(f"Chat ID: `{cid}`", parse_mode="Markdown")


async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Отправляю ежедневный отчёт...")
    try:
        text = get_today_report()
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info("Отчёт отправлен.")
    except Exception as e:
        logger.error(f"Ошибка: {e}")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("chatid", cmd_chatid))

    job_queue = app.job_queue
    job_queue.run_daily(
        send_daily_report,
        time=datetime.now(MOSCOW_TZ).replace(
            hour=REPORT_HOUR,
            minute=REPORT_MINUTE,
            second=0,
            microsecond=0
        ).timetz(),
    )

    logger.info(f"Бот запущен! Отчёт в {REPORT_HOUR:02d}:{REPORT_MINUTE:02d} МСК")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
