import asyncio
import base64
import os
import time
from typing import Optional, Tuple

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Конфіг з оточення (env)
CLIENT_ID = os.getenv("CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
SENDER_NAME = os.getenv("SENDER_NAME", "messagedesk").strip()  # зареєстроване альфа-ім'я
USE_SANDBOX = os.getenv("USE_SANDBOX", "true").lower() in {"1", "true", "yes", "on"}

AUTH_URL = "https://api-gateway.kyivstar.ua/idp/oauth2/token"
SMS_URL = (
    "https://api-gateway.kyivstar.ua/sandbox/rest/v1beta/sms"
    if USE_SANDBOX
    else "https://api-gateway.kyivstar.ua/rest/v1/sms"
)

# Налаштування кеша токена
TOKEN_SAFETY_MARGIN_SECONDS = 60  # оновлювати трохи раніше завершення дії
DEFAULT_TOKEN_TTL_SECONDS = 8 * 60 * 60  # fallback: 8 годин (як у документації)
_cached_access_token: Optional[str] = None
_cached_token_expiry_ts: float = 0.0

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


def _validate_config() -> Optional[str]:
    if not TELEGRAM_TOKEN:
        return "Не задано TELEGRAM_TOKEN"
    if not CLIENT_ID or not CLIENT_SECRET:
        return "Не задано CLIENT_ID/CLIENT_SECRET"
    if not SENDER_NAME:
        return "Не задано SENDER_NAME"
    return None


def _map_error_message(status_code: Optional[int], response_text: str) -> str:
    if status_code == 400:
        return f"400 Bad Request: Некоректні параметри запиту. {response_text}"
    if status_code == 401:
        return f"401 Unauthorized: Невірний/протермінований токен або Client credentials. {response_text}"
    if status_code == 403:
        return f"403 Forbidden: Немає доступу до запитуваного ресурсу. {response_text}"
    if status_code == 500:
        return f"500 Internal Server Error: Проблема на стороні сервера провайдера. {response_text}"
    return response_text


def invalidate_kyivstar_token_cache() -> None:
    global _cached_access_token, _cached_token_expiry_ts
    _cached_access_token = None
    _cached_token_expiry_ts = 0.0


def _build_basic_auth_header(client_id: str, client_secret: str) -> str:
    """
    Формуємо Basic auth значення:
    1) об'єднуємо `client_id:client_secret`
    2) кодуємо у bytes через UTF-8
    3) base64-кодуємо bytes
    4) декодуємо bytes назад у str для HTTP заголовка
    """
    auth_str = f"{client_id}:{client_secret}"
    auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    return f"Basic {auth_base64}"


def get_kyivstar_token(force_refresh: bool = False) -> Optional[str]:
    """
    Повертає access token з кеша або запитує новий.

    - якщо token ще дійсний (з урахуванням safety margin) — повертає кеш
    - інакше виконує OAuth client_credentials запит
    - враховує `expires_in` з відповіді
    - якщо `expires_in` відсутній/битий — використовує fallback 8 годин
    """
    global _cached_access_token, _cached_token_expiry_ts

    now = time.time()
    if (
        not force_refresh
        and _cached_access_token
        and now < (_cached_token_expiry_ts - TOKEN_SAFETY_MARGIN_SECONDS)
    ):
        return _cached_access_token

    headers = {
        "Authorization": _build_basic_auth_header(CLIENT_ID, CLIENT_SECRET),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials"}

    try:
        r = requests.post(AUTH_URL, headers=headers, data=data, timeout=10)
        print("Auth status:", r.status_code)
        r.raise_for_status()

        body = r.json()
        access_token = body.get("access_token")
        expires_raw = body.get("expires_in", DEFAULT_TOKEN_TTL_SECONDS)
        try:
            expires_in = int(expires_raw)
            if expires_in <= 0:
                expires_in = DEFAULT_TOKEN_TTL_SECONDS
        except (TypeError, ValueError):
            expires_in = DEFAULT_TOKEN_TTL_SECONDS

        if not access_token:
            print("Auth error: access_token відсутній у відповіді")
            return None

        _cached_access_token = access_token
        _cached_token_expiry_ts = now + expires_in
        return access_token
    except Exception as e:
        print(f"Auth error: {e}")
        if "r" in locals():
            print("Auth response:", r.text)
        return None


def send_kyivstar_sms(token: str, phone: str, text: str) -> Tuple[Optional[requests.Response], str]:
    if not token:
        return None, "Токен не отримано"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": SENDER_NAME,
        "to": phone.lstrip("+"),
        "text": text,
    }

    try:
        r = requests.post(SMS_URL, json=payload, headers=headers, timeout=10)
        return r, r.text
    except Exception as e:
        return None, f"Помилка запиту до SMS API: {e}"


@dp.message(Command("start"))
async def start(message: types.Message):
    mode = "ПІСОЧНИЦЯ (тест)" if USE_SANDBOX else "ПРОДАКШН (реальні SMS!)"
    await message.answer(f"Бот готовий ({mode}). Надішли: `380971234567 Тестове повідомлення`")


@dp.message()
async def handle_sms(message: types.Message):
    if not message.text:
        return await message.answer("Надішли текст у форматі: 380971234567 Текст повідомлення")

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Формат: 380971234567 Текст повідомлення")

    phone, text = parts
    if not phone.startswith("380") or len(phone) != 12 or not phone.isdigit():
        return await message.answer("Номер у форматі 380971234567 (без +)")

    token = get_kyivstar_token()
    if not token:
        return await message.answer("❌ Не вдалося отримати токен від Київстар. Перевір лог бота.")

    res, response_text = send_kyivstar_sms(token, phone, text)

    if res and res.status_code == 401:
        invalidate_kyivstar_token_cache()
        refreshed_token = get_kyivstar_token(force_refresh=True)
        if refreshed_token:
            res, response_text = send_kyivstar_sms(refreshed_token, phone, text)

    if res and res.status_code in (200, 201, 202):
        await message.answer(f"✅ SMS надіслано на {phone} (пісочниця/тест)")
    else:
        status_code = res.status_code if res else None
        mapped = _map_error_message(status_code, response_text)
        err = f"❌ Помилка {status_code if status_code is not None else 'запиту'}:\n{mapped}"
        await message.answer(err)
        print(err)


async def main():
    config_error = _validate_config()
    if config_error:
        raise RuntimeError(f"Помилка конфігурації: {config_error}")

    print("Бот запущено. Використовується:", "SANDBOX" if USE_SANDBOX else "PROD")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
