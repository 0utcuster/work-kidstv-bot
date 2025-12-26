Запуск:

1) python3 -m venv venv
2) source venv/bin/activate
3) pip install -r requirements.txt
4) cp .env.example .env и заполните BOT_TOKEN + ADMIN_IDS
5) python -m app.main

SQLite файл создастся как bot.db рядом с проектом.

Команды:
- /start
- /admin (только для ADMIN_IDS)