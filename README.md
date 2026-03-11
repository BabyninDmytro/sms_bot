# SMS Bot (Kyivstar + Telegram)

Проєкт для відправки SMS через Kyivstar API з Telegram.

Підтримує два окремі сценарії роботи:
- `bot_main.py` — Telegram-бот (aiogram), який приймає команду з номером і текстом та надсилає SMS вручну.
- `telethon_listener.py` — listener (Telethon), який слухає задані чати/канали, шукає ключові слова та відправляє SMS-алерти автоматично.

## Можливості
- Отримання OAuth2 токена Kyivstar (`client_credentials`) з кешуванням і автооновленням.
- Відправка SMS через sandbox або production endpoint.
- Перевірка та нормалізація українських мобільних номерів (`380...` / `+380...`).
- Обробка типових помилок API (`400/401/403/413/422/500`) у зрозумілому вигляді.
- Retry відправки після `401` (refresh token + повторний запит).
- Unit-тести для конфігурації, валідації номерів і мапінгу помилок.

## Структура репозиторію
- `bot_main.py` — вхідна точка для aiogram-бота.
- `telethon_listener.py` — вхідна точка для Telethon listener.
- `kyivstar_client.py` — клієнт для auth + send SMS.
- `config.py` — завантаження/парсинг конфігурації з ENV.
- `validators.py` — нормалізація та валідація телефонів.
- `tests/` — автотести.

## Вимоги
- Python 3.10+
- Telegram Bot Token (для `bot_main.py`)
- Kyivstar API credentials (`CLIENT_ID`, `CLIENT_SECRET`)
- Для listener: `TELETHON_API_ID`, `TELETHON_API_HASH`

## Встановлення
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Налаштування змінних середовища
Створіть `.env` у корені проєкту (приклад значень):

```env
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
TELEGRAM_TOKEN=your_telegram_bot_token
SENDER_NAME=messagedesk
USE_SANDBOX=true
MAX_SMS_TEXT_LENGTH=255
MAX_SMS_SEGMENTS=6

TELETHON_API_ID=123456
TELETHON_API_HASH=your_api_hash
TELETHON_SESSION_NAME=telethon_sms_listener
TELETHON_WATCH_CHATS=my_channel,-1001234567890
TELETHON_KEYWORDS=тривога,alarm,critical
TELETHON_ALERT_PHONES=380971234567,380501112233
TELETHON_DEDUPE_SECONDS=1800
TELETHON_MAX_SMS_CHARS=180
```

## Окремо про `bot_main.py`
`bot_main.py` — це інтерактивний бот на `aiogram`:
- Обробляє `/start`.
- Приймає повідомлення формату:
  - `380971234567 Текст повідомлення`
  - `+380971234567 Текст повідомлення`
- Перевіряє номер і довжину тексту (`MAX_SMS_TEXT_LENGTH`).
- Викликає Kyivstar API для відправки SMS.
- Повертає користувачу статус (успіх/помилка).

Запуск:
```bash
python bot_main.py
```

## Окремо про `telethon_listener.py`
`telethon_listener.py` — фоновий listener на `Telethon`:
- Підключається як Telegram-клієнт за `TELETHON_API_ID` / `TELETHON_API_HASH`.
- Слухає нові повідомлення в чатах із `TELETHON_WATCH_CHATS`.
- Шукає ключові слова з `TELETHON_KEYWORDS`.
- Для релевантного повідомлення формує SMS-алерт:
  - додає назву/ідентифікатор чату,
  - ключове слово,
  - скорочений текст,
  - посилання на повідомлення.
- Уникає дублювань через TTL-кеш (`TELETHON_DEDUPE_SECONDS`).
- Надсилає алерти на номери з `TELETHON_ALERT_PHONES`.

Запуск:
```bash
python telethon_listener.py
```

> Під час першого запуску Telethon може попросити авторизацію акаунта (номер, код, 2FA якщо ввімкнено).

## Тести
```bash
python -m unittest discover -s tests -p 'test_*.py'
```

## Безпека та експлуатація
- У production (`USE_SANDBOX=false`) SMS можуть тарифікуватися.
- Не комітьте `.env` та секрети в git.
- Для стабільної роботи listener-а бажано запускати через supervisor/systemd/docker restart policy.
