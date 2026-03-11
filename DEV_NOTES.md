# DEV Notes

## 2026-03-09

### Автентифікація Kyivstar API: покращення
- Перенесено конфігурацію з хардкоду у змінні оточення:
  - `CLIENT_ID`
  - `CLIENT_SECRET`
  - `TELEGRAM_TOKEN`
  - `SENDER_NAME`
  - `USE_SANDBOX`
- Додано валідацію обов'язкових змінних конфігурації при старті.
- Реалізовано in-memory кеш access token:
  - збереження `access_token`
  - збереження часу протухання за `expires_in`
  - safety margin (оновлення токена заздалегідь).
- Додано примусову інвалідацію кеша токена.
- Додано retry-логіку при `401 Unauthorized`:
  - інвалідація кеша
  - повторне отримання токена
  - один повторний SMS-запит.
- Додано мапінг помилок API для статусів `400/401/403/500` у більш зрозумілі повідомлення.
- Виправлено текстову опечатку в повідомленні про успішну відправку (`пісочниця`).

### Уточнення після ревʼю (auth/base64/token TTL)
- Уточнено формування Basic Auth у окремій функції `_build_basic_auth_header(...)` з поясненням кроків кодування (`utf-8` -> `base64` -> string для HTTP заголовка).
- Додано docstring до `get_kyivstar_token()` з явною логікою кеша/оновлення.
- Явно враховано 8-годинний TTL токена: додано `DEFAULT_TOKEN_TTL_SECONDS = 8 * 60 * 60` як fallback, якщо `expires_in` невалідний або відсутній у відповіді.
- Значення `CLIENT_ID`, `CLIENT_SECRET`, `TELEGRAM_TOKEN` залишаються тільки з env (без хардкоду), додано `.strip()` для захисту від випадкових пробілів.

### Оновлення обробки відповідей SMS API
- Розширено мапінг помилок відправки SMS для статусів:
  - `413 Payload Too Large` — окреме повідомлення, що текст SMS завеликий.
  - `422 Unprocessable Entity` — окреме повідомлення про помилку валідації вмісту запиту.
- Це враховує фактичні коди відповідей, які повертає API під час відправки SMS (`200/400/401/403/413/422`).

### Уточнення успішних кодів SMS API
- Логіку успіху відправки SMS звужено до `HTTP 200`.
- Коди `201/202` більше не трактуються як успішна відправка, щоб уникнути хибнопозитивного статусу при зміні поведінки API.
- Якщо API поверне `201/202`, бот покаже це як неуспішний результат із текстом відповіді сервера.

### Гнучкіший формат вводу номера
- Оновлено валідацію номера в Telegram-повідомленні: бот приймає як `380...`, так і `+380...`.
- Перед перевіркою і відправкою номер нормалізується через `lstrip("+")`, щоб на API завжди йшов формат без плюса (`380...`).
- Оновлено підказку користувачу у повідомленні про помилку формату номера.

## 2026-03-10

### Покращення зі списку 2-9 (без async HTTP)
- Розбито код на модулі для кращої підтримки:
  - `config.py` — завантаження/валідація налаштувань з env.
  - `kyivstar_client.py` — логіка токена, відправки SMS і мапінг API-помилок.
  - `validators.py` — нормалізація і валідація номера телефону.
- Додано кореляційний ID у логи (`chat_id:message_id`) для наскрізного трейсингу одного запиту користувача.
- Прибрано широкі `except Exception`: додано окрему обробку `Timeout`, `ConnectionError`, `HTTPError`, `RequestException`.
- Зменшено ризик витоку чутливих даних у логах: не логуються повні auth response payload з токенами.
- Усунуто дублювання нормалізації номера: тепер номер нормалізується в handler і в API клієнт передається вже у канонічному форматі.
- Посилено валідацію номера: окрім формату `380XXXXXXXXX`, перевіряється валідний мобільний код України.
- Додано pre-check довжини тексту SMS перед викликом API (`MAX_SMS_TEXT_LENGTH`, за замовчуванням 255).
- Додано більш інформативний стартовий лог: mode + endpoint, і warning при PROD режимі.
- Оновлено `.env.example` (`MAX_SMS_TEXT_LENGTH`) для керованої бізнес-валідації довжини SMS.
### Парсинг номера на початку рядка через regex
- Оновлено розбір вхідного повідомлення в `bot_main.py`: замість `split(maxsplit=1)` використовується regex, який виділяє номер на початку рядка і текст після нього.
- Підтримано формат номера з пробілами між цифрами, наприклад: `+380 97 123 45 67 Тест`.
- Нормалізацію номера посилено: `normalize_phone()` тепер прибирає всі whitespace-символи (не лише пробіл), після чого видаляє префікс `+`.
- Прибрано службовий `print(...)` з handler, щоб уникнути зайвого виводу в stdout.

### Graceful shutdown при ручній зупинці (Ctrl+C) на Windows
- Оновлено блок запуску в `__main__`:
  - `asyncio.run(main())` обгорнуто в `try/except KeyboardInterrupt`, щоб коректно обробляти ручну зупинку.
  - У `finally` додано явне закриття `bot.session` (якщо вона ще відкрита), щоб зменшити ймовірність `RuntimeError: Event loop is closed` під час фіналізації транспорту в Windows ProactorEventLoop.
- Додано інформативний лог при отриманні `KeyboardInterrupt`.

### Виправлення shutdown після ревʼю (AiohttpSession.closed)
- Виявлено, що в `aiogram`-сесії (`AiohttpSession`) немає атрибуту `closed`, тому перевірка `if not bot.session.closed` спричиняла `AttributeError` при зупинці.
- Shutdown-логіку перенесено в `main()`:
  - `dp.start_polling(bot)` обгорнуто в `try/finally`.
  - `await bot.session.close()` виконується в `finally` у межах того ж event loop.
- У `__main__` залишено лише перехоплення `KeyboardInterrupt` для чистого завершення без зайвого traceback.

### Shutdown (Варіант A): фіналізація в `main()`
- Уточнено реалізацію graceful shutdown за Варіантом A:
  - `KeyboardInterrupt` перехоплюється в `main()` навколо `dp.start_polling(bot)`.
  - Закриття `bot.session` лишається у `finally` того ж event loop.
- Точка входу спрощена до `asyncio.run(main())` без дублюючого перехоплення переривання в `__main__`.
- Додано безпечний логований fallback на `RuntimeError` під час закриття сесії, щоб уникати зайвого traceback при завершенні.

### Локальна pre-check перевірка сегментів SMS + провайдерна межа `maxSegments`
- Додано розрахунок SMS-метрик у `validators.py`:
  - визначення кодування `GSM-7` / `Unicode`;
  - підрахунок умовної довжини (`units`) з урахуванням GSM extension-символів, що займають 2 юніти;
  - обчислення кількості сегментів за правилами `160/153` (GSM-7) та `70/67` (Unicode).
- У `bot_main.py` додано pre-check перед API-викликом:
  - якщо потрібна кількість сегментів більша за дозволену (`MAX_SMS_SEGMENTS`) — бот відхиляє запит локально з деталями (кодування, довжина, сегменти);
  - збережено окремий локальний guard за `MAX_SMS_TEXT_LENGTH` як додаткову бізнес-межу.
- У `kyivstar_client.py` метод `send_sms()` тепер передає `maxSegments` у payload, щоб провайдер виконував остаточну перевірку ліміту сегментів.
- Повідомлення про успіх у `bot_main.py` покращено:
  - якщо API повертає `reservedSmsSegments`, бот показує фактично зарезервовані сегменти;
  - якщо поля немає, бот показує локальну pre-check оцінку сегментів.
- У `config.py` додано `MAX_SMS_SEGMENTS` (діапазон 1..6, дефолт 6) як конфігурований ліміт для локальної та API-перевірки.

### Спрощення перевірки розміру SMS (provider-first)
- Прибрано складну локальну pre-check логіку сегментації (GSM/Unicode та локальний розрахунок сегментів).
- Бот тепер працює за простим сценарієм:
  - завжди передає `MAX_SMS_SEGMENTS` у запит до SMS API;
  - рішення про завеликий текст приймає провайдер;
  - якщо API відхиляє запит (зокрема `413`), користувач отримує повідомлення про завеликий текст через стандартний мапінг помилок.
- Видалено тести локального калькулятора сегментів, оскільки ця логіка більше не використовується.

## 2026-03-11

### Корекція після рев'ю
- Залишено async-інтеграцію з Kyivstar через `aiohttp` (`get_token/send_sms` + закриття сесії в shutdown).
- Залишено pre-check довжини SMS у `handle_sms` через `settings.max_sms_text_length`.
- Прибрано структуровані JSON-логи та файловий лог `bot.log` (`RotatingFileHandler`) — повернуто звичне текстове логування.
- Прибрано runtime-метрики/лічильники (`sms_success_count`, `sms_failed_count`, `retry`, 4xx/5xx ratio, token timing), як зайві для поточного етапу.
- Збережено додані unit-тести для `validators`, `map_error_message`, `config`.

### Telethon listener (Варіант 2: production-lite)
- Додано окремий процес `telethon_listener.py` для моніторингу Telegram чатів/каналів через Telethon:
  - слухає `NewMessage` у вказаних чатах;
  - шукає ключові слова (`TELETHON_KEYWORDS`);
  - відкидає дублікати за TTL (`TELETHON_DEDUPE_SECONDS`) через in-memory dedupe cache;
  - формує SMS-алерт із префіксом `[chat] keyword`, коротким текстом та лінком на повідомлення (`t.me/...` / `t.me/c/...`).
- Інтеграція з існуючим `KyivstarClient` виконана без зміни основного `aiogram`-бота:
  - для блокуючих HTTP-викликів використано `asyncio.to_thread(...)`;
  - збережено retry при `401` (refresh токена + повторний SMS-запит).
- Додано нові env-параметри в `config.py` для Telethon-пайплайна:
  - `TELETHON_API_ID`, `TELETHON_API_HASH`, `TELETHON_SESSION_NAME`
  - `TELETHON_WATCH_CHATS`, `TELETHON_KEYWORDS`, `TELETHON_ALERT_PHONES`
  - `TELETHON_DEDUPE_SECONDS`, `TELETHON_MAX_SMS_CHARS`
- Оновлено `requirements.txt`: додано `telethon` та `requests` як явні залежності.

### Оновлення `.env.example` для Telethon listener
- Додано всі нові змінні оточення, які були введені для `telethon_listener.py`, щоб запуск не вимагав ручного пошуку полів у коді:
  - `TELETHON_API_ID`, `TELETHON_API_HASH`, `TELETHON_SESSION_NAME`
  - `TELETHON_WATCH_CHATS`, `TELETHON_KEYWORDS`, `TELETHON_ALERT_PHONES`
  - `TELETHON_DEDUPE_SECONDS`, `TELETHON_MAX_SMS_CHARS`
- Додано короткі пояснення у `.env.example` щодо формату списків, джерела `api_id/api_hash` та призначення параметрів dedupe/ліміту довжини SMS.

### Виправлення Telethon listener для async KyivstarClient
- Усунено падіння `TypeError: cannot unpack non-iterable coroutine object` у `telethon_listener.py`.
- Причина: після переходу `KyivstarClient` на async (`aiohttp`) listener все ще викликав `get_token/send_sms` через `asyncio.to_thread(...)`, що повертало coroutine об'єкти.
- Виправлення:
  - замінено виклики на прямі `await kyivstar_client.get_token(...)` та `await kyivstar_client.send_sms(...)`;
  - оновлено перевірку HTTP-статусу на `response.status` (aiohttp), замість `response.status_code`;
  - додано гарантоване закриття HTTP-сесії Kyivstar client у `finally` через `await kyivstar_client.close()`.

### Graceful shutdown для Telethon listener (Ctrl+C / CancelledError)
- Усунено шумний traceback при ручній зупинці listener-а (`Ctrl+C`), де з'являвся ланцюжок `CancelledError` -> `KeyboardInterrupt`.
- У `telethon_listener.py` додано явну обробку `(asyncio.CancelledError, KeyboardInterrupt)` навколо `run_until_disconnected()` з інформативним логом штатного завершення.
- У `__main__` додано перехоплення `KeyboardInterrupt`, щоб завершення процесу не виглядало як помилка для користувача.

### README документація проєкту
- Створено новий `README.md` з базовим описом призначення проєкту, можливостей, структури репозиторію та кроків встановлення.
- Додано окремі секції для двох точок входу:
  - `bot_main.py` (ручна відправка SMS через Telegram-бота на aiogram),
  - `telethon_listener.py` (автоматичні SMS-алерти з Telegram-чатів через Telethon).
- Задокументовано приклад `.env` з усіма ключовими змінними для обох сценаріїв.
- Додано інструкції запуску та запуску тестів.
