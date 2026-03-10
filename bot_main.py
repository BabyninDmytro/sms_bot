import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from config import load_settings, validate_settings
from kyivstar_client import KyivstarClient, map_error_message
from validators import normalize_phone, validate_phone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

settings = load_settings()
bot = Bot(token=settings.telegram_token)
dp = Dispatcher()
kyivstar_client = KyivstarClient(settings)
MESSAGE_PATTERN = re.compile(r"^\s*(?P<phone>\+?\s*3\s*8\s*0(?:\s*\d){9})\s+(?P<text>.+?)\s*$")


@dp.message(Command("start"))
async def start(message: types.Message):
    mode = "ПІСОЧНИЦЯ (тест)" if settings.use_sandbox else "ПРОДАКШН (реальні SMS!)"
    await message.answer(f"Бот готовий ({mode}). Надішли: `380971234567 Тестове повідомлення`")


@dp.message()
async def handle_sms(message: types.Message):
    cid = f"{message.chat.id}:{message.message_id}"

    if not message.text:
        return await message.answer("Надішли текст у форматі: 380971234567 Текст повідомлення")

    match = MESSAGE_PATTERN.match(message.text)
    if not match:
        return await message.answer("Формат: 380971234567 Текст повідомлення")

    phone_input = match.group("phone")
    text = match.group("text")
    phone = normalize_phone(phone_input)

    phone_error = validate_phone(phone)
    if phone_error:
        logger.info("[cid=%s] invalid phone input=%s", cid, phone_input)
        return await message.answer(phone_error)

    if len(text) > settings.max_sms_text_length:
        logger.info("[cid=%s] sms text too long len=%s", cid, len(text))
        return await message.answer(
            f"Текст SMS завеликий: {len(text)} символів. Максимум: {settings.max_sms_text_length}."
        )

    token = kyivstar_client.get_token(cid=cid)
    if not token:
        return await message.answer("❌ Не вдалося отримати токен від Київстар. Перевір лог бота.")

    response, response_text = kyivstar_client.send_sms(cid=cid, token=token, phone=phone, text=text)

    if response and response.status_code == 401:
        logger.info("[cid=%s] sms returned 401, refreshing token", cid)
        kyivstar_client.invalidate_token_cache()
        refreshed_token = kyivstar_client.get_token(cid=cid, force_refresh=True)
        if refreshed_token:
            response, response_text = kyivstar_client.send_sms(
                cid=cid,
                token=refreshed_token,
                phone=phone,
                text=text,
            )

    if response and response.status_code == 200:
        await message.answer(f"✅ SMS надіслано на {phone} (пісочниця/тест)")
        return

    status_code = response.status_code if response else None
    mapped = map_error_message(status_code, response_text)
    err = f"❌ Помилка {status_code if status_code is not None else 'запиту'}:\n{mapped}"
    logger.error("[cid=%s] sms send failed status=%s", cid, status_code)
    await message.answer(err)


async def main():
    config_error = validate_settings(settings)
    if config_error:
        raise RuntimeError(f"Помилка конфігурації: {config_error}")

    mode = "SANDBOX" if settings.use_sandbox else "PROD"
    logger.info("Бот запущено. Mode=%s endpoint=%s", mode, settings.sms_url)
    if not settings.use_sandbox:
        logger.warning("Увімкнено PROD режим: SMS можуть тарифікуватися")

    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Отримано KeyboardInterrupt, зупиняємо бота...")
    finally:
        try:
            await bot.session.close()
        except RuntimeError as exc:
            logger.warning("Помилка під час закриття bot.session: %s", exc)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Отримано KeyboardInterrupt, зупиняємо бота...")
    finally:
        if not bot.session.closed:
            asyncio.run(bot.session.close())
