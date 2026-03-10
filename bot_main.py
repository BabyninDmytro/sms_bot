import asyncio
import base64
import os

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# Завантажує змінні з .env у поточне середовище
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
SENDER_NAME = os.getenv("SENDER_NAME", "messagedesk").strip()
USE_SANDBOX = os.getenv("USE_SANDBOX", "true").lower() in {"1", "true", "yes", "on"}

AUTH_URL = "https://api-gateway.kyivstar.ua/idp/oauth2/token"

if USE_SANDBOX:
    SMS_URL = "https://api-gateway.kyivstar.ua/sandbox/rest/v1beta/sms"
else:
    SMS_URL = "https://api-gateway.kyivstar.ua/rest/v1/sms"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


def validate_config() -> str | None:
    if not TELEGRAM_TOKEN:
        return "Не задано TELEGRAM_TOKEN (перевір .env)"
    if not CLIENT_ID or not CLIENT_SECRET:
        return "Не задано CLIENT_ID/CLIENT_SECRET (перевір .env)"
    if not SENDER_NAME:
        return "Не задано SENDER_NAME (перевір .env)"
    return None


def get_kyivstar_token():
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials"}

    try:
        r = requests.post(AUTH_URL, headers=headers, data=data, timeout=10)
        print("Auth status:", r.status_code)
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        print(f"Auth error: {e}")
        if "r" in locals():
            print("Auth response:", r.text)
        return None


def send_kyivstar_sms(token, phone, text):
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
        return None, str(e)


@dp.message(Command("start"))
async def start(message: types.Message):
    mode = "ПІСОЧНИЦЯ (тест)" if USE_SANDBOX else "ПРОДАКШН (реальні SMS!)"
    await message.answer(f"Бот готовий ({mode}). Надішли: `380971234567 Тестове повідомлення`")


@dp.message()
async def handle_sms(message: types.Message):
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Формат: 380971234567 Текст повідомлення")

    phone, text = parts
    if not phone.startswith("380") or len(phone) != 12:
        return await message.answer("Номер у форматі 380971234567 (без +)")

    token = get_kyivstar_token()
    if not token:
        return await message.answer("❌ Не вдалося отримати токен від Київстар. Перевір консоль бота.")

    res, response_text = send_kyivstar_sms(token, phone, text)

    if res and res.status_code in (200, 201, 202):
        await message.answer(f"✅ SMS надіслано на {phone} (пісочниця/тест)")
    else:
        err = f"❌ Помилка {res.status_code if res else 'запиту'}:\n{response_text}"
        await message.answer(err)
        print(err)


async def main():
    config_error = validate_config()
    if config_error:
        raise RuntimeError(config_error)

    print("Бот запущено. Використовується:", "SANDBOX" if USE_SANDBOX else "PROD")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
