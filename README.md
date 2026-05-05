# 📊 Telegram Бот — Ежедневный отчёт из Google Таблицы

Бот каждый день в **12:00 МСК** отправляет отчёт в Telegram-группу.

---

## 🚀 Быстрый старт

### Шаг 1 — Создай Telegram бота

1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Напиши `/newbot` → придумай имя и username
3. Скопируй **токен** (вида `123456:ABC-DEF...`)

---

### Шаг 2 — Узнай ID своей группы

1. Добавь бота в группу
2. Напиши в группе `/chatid`
3. Бот ответит числом вида `-1001234567890` — это и есть `GROUP_CHAT_ID`

---

### Шаг 3 — Настрой Google Service Account

1. Перейди на [console.cloud.google.com](https://console.cloud.google.com)
2. Создай новый проект (или выбери существующий)
3. Включи **Google Sheets API** и **Google Drive API**:
   - Меню → APIs & Services → Enable APIs
   - Найди и включи оба
4. Создай Service Account:
   - APIs & Services → Credentials → Create Credentials → Service Account
   - Дай любое имя, нажми Create
5. Открой созданный аккаунт → вкладка **Keys** → Add Key → JSON
6. Скачается файл `credentials.json` — он понадобится в шаге 5

---

### Шаг 4 — Дай доступ к таблице

1. Открой скачанный `credentials.json`
2. Найди поле `"client_email"` — скопируй этот email
3. Открой свою Google Таблицу
4. Нажми **Настройки доступа** → вставь email → роль **Редактор** (или Читатель)

---

### Шаг 5 — Разверни на Railway

1. Загрузи файлы проекта на [GitHub](https://github.com) (новый репозиторий)
2. Зайди на [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Выбери репозиторий
4. Перейди в **Variables** и добавь переменные окружения:

| Переменная | Значение |
|---|---|
| `TELEGRAM_TOKEN` | токен от BotFather |
| `GROUP_CHAT_ID` | ID группы (например `-1001234567890`) |
| `SPREADSHEET_ID` | ID таблицы из URL (между `/d/` и `/edit`) |
| `SHEET_NAME` | название листа (например `Лист1`) |
| `GOOGLE_CREDENTIALS_JSON` | **всё содержимое** файла credentials.json |
| `REPORT_HOUR` | `12` |
| `REPORT_MINUTE` | `0` |

> ⚠️ `GOOGLE_CREDENTIALS_JSON` — вставляй весь JSON одной строкой как есть

5. Railway автоматически запустит бота!

---

### Альтернатива — Render.com

1. Загрузи на GitHub
2. [render.com](https://render.com) → New → Background Worker
3. Добавь те же переменные окружения
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python bot.py`

---

## 📋 Команды бота

| Команда | Действие |
|---|---|
| `/start` | Запустить бота, список команд |
| `/report` | Получить отчёт прямо сейчас |
| `/chatid` | Узнать ID текущего чата |

---

## 📁 Структура проекта

```
tg-report-bot/
├── bot.py              # основной код бота
├── requirements.txt    # зависимости
├── Procfile            # для Railway/Render
└── README.md           # эта инструкция
```

---

## ❓ Частые вопросы

**Бот не отправляет отчёт автоматически?**
Убедись что бот добавлен в группу и ему дали права на отправку сообщений.

**Ошибка "Forbidden: bot was kicked"?**
Бот был удалён из группы. Добавь снова и проверь GROUP_CHAT_ID.

**Таблица не читается?**
Проверь что service account email добавлен в доступ к таблице (Шаг 4).

**Как изменить время отправки?**
Измени переменные `REPORT_HOUR` и `REPORT_MINUTE` в настройках Railway.
