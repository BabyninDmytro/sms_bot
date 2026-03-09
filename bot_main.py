import asyncio
import requests
import base64
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Твої дані (з кабінету)
CLIENT_ID = '5f08282c-c11e-46b3-ae43-0834cc519c17'
CLIENT_SECRET = 'bpcivTRk5XClKs0tA0qyI46aQu'
TELEGRAM_TOKEN = '8727067916:AAHflSa95hpf7WtD8jHZbvNZscYWprGlgh0'
SENDER_NAME = 'messagedesk'  # твоє зареєстроване альфа-ім'я

# ────────────────────────────────────────────────
USE_SANDBOX = True  # True = пісочниця (тест), False = production (реальні SMS, тарифікується!)

AUTH_URL = "https://api-gateway.kyivstar.ua/idp/oauth2/token"

if USE_SANDBOX:
    SMS_URL = "https://api-gateway.kyivstar.ua/sandbox/rest/v1beta/sms"
else:
    SMS_URL = "https://api-gateway.kyivstar.ua/rest/v1/sms"  # або /rest/v1beta/sms — перевір у кабінеті

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

def get_kyivstar_token():
    # Basic Auth: base64(client_id:client_secret)
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_bytes = auth_str.encode('utf-8')
    auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')

    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }

    try:
        r = requests.post(AUTH_URL, headers=headers, data=data, timeout=10)
        print("Auth status:", r.status_code)
        print("Auth response:", r.text)  # для дебагу в консолі
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        print(f"Auth error: {e}")
        if 'r' in locals():
            print("Response:", r.text)
        return None

def send_kyivstar_sms(token, phone, text):
    if not token:
        return None, "Токен не отримано"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": SENDER_NAME,
        "to": phone.lstrip('+'),  # 38097...
        "text": text
    }

    try:
        print("Sending SMS to:", SMS_URL)
        print("Payload:", payload)
        r = requests.post(SMS_URL, json=payload, headers=headers, timeout=10)
        print("SMS status:", r.status_code)
        print("SMS response:", r.text)
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
    if not phone.startswith('380') or len(phone) != 12:
        return await message.answer("Номер у форматі 380971234567 (без +)")

    token = get_kyivstar_token()
    if not token:
        return await message.answer("❌ Не вдалося отримати токен від Київстар. Перевір консоль бота.")

    res, response_text = send_kyivstar_sms(token, phone, text)

    if res and res.status_code in (200, 201, 202):
        await message.answer(f"✅ SMS надіслано на {phone} (піточниця/тест)")
    else:
        err = f"❌ Помилка {res.status_code if res else 'запиту'}:\n{response_text}"
        await message.answer(err)
        print(err)  # лог в консоль

async def main():
    print("Бот запущено. Використовується:", "SANDBOX" if USE_SANDBOX else "PROD")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())