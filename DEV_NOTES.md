# DEV Notes

## 2026-03-10

### Fix завантаження .env через python-dotenv
- Додано `load_dotenv()` у `bot_main.py`, щоб бот автоматично підхоплював значення з `.env`.
- Конфіг (`CLIENT_ID`, `CLIENT_SECRET`, `TELEGRAM_TOKEN`, `SENDER_NAME`, `USE_SANDBOX`) тепер читається з env.
- Додано `validate_config()` з fail-fast перевіркою обовʼязкових змінних та явними підказками “перевір .env”.
- Додано `.env.example` як шаблон для локального запуску.
