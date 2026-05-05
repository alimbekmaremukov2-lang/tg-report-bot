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
 
# Точные столбцы (0-based) где находятся значения в строке 5
FIELDS = [
    {"name": "Количество обработанного товара", "col": 0},
    {"name": "ЗП НА ЕД ТОВАРА",                "col": 2},
    {"name": "Сумма обработанного товара",      "col": 3},
    {"name": "Кол-во коробок",                  "col": 5},
    {"name": "Сумма за хранение товара",        "col": 7},
    {"name": "Сумма заработной платы",          "col": 9},
    {"name": "Общая выручка",                   "col": 11},
    {"name": "Траты на сегодняшний день",       "col": 13},
    {"name": "Маржа",                           "col": 14},
    {"name": "Продуктивность команды",          "col": 15},
]
 
 
def get_gclient():
    creds_data = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON", ""))
    creds = Credentials.from_service_account_info(creds_data, scopes=[
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ])
    return gspread.authorize(creds)
 
 
def get_today_report():
    today = datetime.now(MOSCOW_TZ)
    try:
        gc = get_gclient()
        sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        all_values = sheet.get_all_values()
 
        # Дата — строка 3 (индекс 2)
        date_val = ""
        for cell in all_values[2]:
            if cell.strip():
                date_val = cell.strip()
                break
        if not date_val:
            date_val = today.strftime("%d.%m.%Y")
 
        # Значения — строка 5 (индекс 4)
        row5 = all_values[4] if len(all_values) > 4 else []
 
        # Детализация из Q5 (индекс 16) и R5 (индекс 17)
        sum_detail = row5[16].strip() if len(row5) > 16 else ""
        prod_detail = row5[17].strip() if len(row5) > 17 else ""
 
        # Список товара — строки 9-12 (индексы 8-11)
        goods_rows = []
        for r in all_values[8:12]:
            name = r[0].strip() if len(r) > 0 else ""
            qty = r[1].strip() if len(r) > 1 else ""
            if name and name not in ("Список товара", "кол-во", ""):
                goods_rows.append((name, qty))
 
        # Клиенты — строки 14-23 (индексы 13-22)
        client_rows = []
        for r in all_values[13:23]:
            if len(r) > 4 and r[4].strip():
                client_rows.append(r)
 
    except Exception as e:
        logger.error(f"Ошибка чтения таблицы: {e}")
        return f"Ошибка при чтении таблицы: {e}"
 
    lines = [
        "📊 *Ежедневный отчёт*",
        f"📅 {date_val}",
        "──────────────────────",
    ]
 
    for field in FIELDS:
        name = field["name"]
        col = field["col"]
        v = row5[col].strip() if col < len(row5) else ""
        if not v:
            continue
 
        lines.append(f"\n*{name}*")
        lines.append(v)
 
        # После кол-ва товара — список товара
        if col == 0 and goods_rows:
            lines.append("📋 *Список товара:*")
            for gname, gqty in goods_rows:
                lines.append(f"• {gname}: {gqty}")
 
        # После суммы обработанного — детализация из Q5
        if col == 3 and sum_detail:
            for line in sum_detail.split("\n"):
                if line.strip():
                    lines.append(f"_{line.strip()}_")
 
        # После продуктивности — детализация из R5
        if col == 15 and prod_detail:
            lines.append("──────────────────────")
            for line in prod_detail.split("\n"):
                if line.strip():
                    lines.append(line.strip())
 
    # Доставка
    if client_rows:
        lines.append("\n──────────────────────")
        lines.append("🚚 *Доставка:*")
        for row in client_rows:
            try:
                name = row[4].strip()
                qty = row[5].strip() if len(row) > 5 else ""
                storage = row[6].strip() if len(row) > 6 else ""
                boxes = row[7].strip() if len(row) > 7 else ""
                costs = row[8].strip() if len(row) > 8 else ""
                revenue = row[9].strip() if len(row) > 9 else ""
                margin = row[10].strip() if len(row) > 10 else ""
                parts = [f"*{name}*"]
                if qty: parts.append(f"{qty} шт")
                if storage: parts.append(storage)
                if boxes: parts.append(f"{boxes} кор")
                if costs: parts.append(f"{costs} р")
                if revenue: parts.append(revenue)
                if margin: parts.append(margin)
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
 
    app.job_queue.run_daily(
        send_daily_report,
        time=datetime.now(MOSCOW_TZ).replace(
            hour=REPORT_HOUR, minute=REPORT_MINUTE, second=0, microsecond=0
        ).timetz(),
    )
 
    logger.info(f"Бот запущен! Отчёт в {REPORT_HOUR:02d}:{REPORT_MINUTE:02d} МСК")
    app.run_polling(drop_pending_updates=True)
 
 
if __name__ == "__main__":
    main()
