import asyncio
import hashlib
import logging
import re
import time
from typing import Optional

from telethon import TelegramClient, events

from config import load_settings
from kyivstar_client import KyivstarClient, map_error_message
from validators import normalize_phone, validate_phone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _sanitize_sms_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _build_message_link(event: events.NewMessage.Event) -> str:
    chat = event.chat
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}/{event.message.id}"

    chat_id = event.chat_id or 0
    private_chat_id = str(abs(int(chat_id)))
    if private_chat_id.startswith("100"):
        private_chat_id = private_chat_id[3:]
    return f"https://t.me/c/{private_chat_id}/{event.message.id}"


class DedupeCache:
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._seen: dict[str, float] = {}

    def is_duplicate(self, key: str) -> bool:
        now = time.time()
        self._cleanup(now)
        expire_at = self._seen.get(key)
        if expire_at and expire_at > now:
            return True
        self._seen[key] = now + self.ttl_seconds
        return False

    def _cleanup(self, now: float) -> None:
        expired_keys = [key for key, expiry in self._seen.items() if expiry <= now]
        for key in expired_keys:
            self._seen.pop(key, None)


async def _send_sms_alert(
    kyivstar_client: KyivstarClient,
    cid: str,
    phone: str,
    text: str,
    max_segments: int,
) -> bool:
    token = await asyncio.to_thread(kyivstar_client.get_token, cid)
    if not token:
        logger.error("[cid=%s] Не вдалося отримати токен Kyivstar", cid)
        return False

    response, response_text = await asyncio.to_thread(
        kyivstar_client.send_sms,
        cid,
        token,
        phone,
        text,
        max_segments,
    )

    if response and response.status_code == 401:
        kyivstar_client.invalidate_token_cache()
        token = await asyncio.to_thread(kyivstar_client.get_token, cid, True)
        if token:
            response, response_text = await asyncio.to_thread(
                kyivstar_client.send_sms,
                cid,
                token,
                phone,
                text,
                max_segments,
            )

    if response and response.status_code == 200:
        return True

    status_code = response.status_code if response else None
    logger.error(
        "[cid=%s] SMS alert failed status=%s details=%s",
        cid,
        status_code,
        map_error_message(status_code, response_text),
    )
    return False


async def main() -> None:
    settings = load_settings()
    kyivstar_client = KyivstarClient(settings)

    if settings.telethon_api_id <= 0 or not settings.telethon_api_hash:
        raise RuntimeError("TELETHON_API_ID/TELETHON_API_HASH не задано")
    if not settings.telethon_watch_chats:
        raise RuntimeError("TELETHON_WATCH_CHATS порожній")
    if not settings.telethon_keywords:
        raise RuntimeError("TELETHON_KEYWORDS порожній")
    if not settings.telethon_alert_phones:
        raise RuntimeError("TELETHON_ALERT_PHONES порожній")

    valid_phones = []
    for phone in settings.telethon_alert_phones:
        normalized = normalize_phone(phone)
        validation_error = validate_phone(normalized)
        if validation_error:
            raise RuntimeError(f"Невалідний номер в TELETHON_ALERT_PHONES: {phone} ({validation_error})")
        valid_phones.append(normalized)

    watch_chat_set = set(settings.telethon_watch_chats)
    dedupe_cache = DedupeCache(ttl_seconds=settings.telethon_dedupe_seconds)

    logger.info(
        "Telethon listener start. chats=%s keywords=%s phones=%s dedupe=%ss",
        list(watch_chat_set),
        list(settings.telethon_keywords),
        valid_phones,
        settings.telethon_dedupe_seconds,
    )

    client = TelegramClient(
        settings.telethon_session_name,
        settings.telethon_api_id,
        settings.telethon_api_hash,
    )

    @client.on(events.NewMessage(incoming=True))
    async def handle_new_message(event: events.NewMessage.Event) -> None:
        chat = await event.get_chat()
        chat_username = getattr(chat, "username", None)
        chat_id_str = str(event.chat_id) if event.chat_id is not None else ""

        if chat_username not in watch_chat_set and chat_id_str not in watch_chat_set:
            return

        raw_text = event.raw_text or ""
        normalized_text = _sanitize_sms_text(raw_text)
        if not normalized_text:
            return

        lowered_text = normalized_text.lower()
        matched_keyword: Optional[str] = next(
            (keyword for keyword in settings.telethon_keywords if keyword in lowered_text),
            None,
        )
        if not matched_keyword:
            return

        dedupe_source = f"{event.chat_id}:{matched_keyword}:{normalized_text}"
        dedupe_key = hashlib.sha256(dedupe_source.encode("utf-8")).hexdigest()
        if dedupe_cache.is_duplicate(dedupe_key):
            logger.info("Skip duplicate alert chat=%s keyword=%s", event.chat_id, matched_keyword)
            return

        message_link = _build_message_link(event)
        chat_name = chat_username or chat_id_str or "unknown"
        prefix = f"[{chat_name}] {matched_keyword}: "
        suffix = f" {message_link}"
        payload_budget = max(20, settings.telethon_max_sms_chars - len(prefix) - len(suffix))
        truncated_text = normalized_text[:payload_budget]
        sms_text = f"{prefix}{truncated_text}{suffix}"

        cid = f"tg:{event.chat_id}:{event.message.id}"
        for phone in valid_phones:
            success = await _send_sms_alert(
                kyivstar_client=kyivstar_client,
                cid=f"{cid}:{phone}",
                phone=phone,
                text=sms_text,
                max_segments=settings.max_sms_segments,
            )
            if success:
                logger.info("[cid=%s] Alert SMS sent to %s", cid, phone)

    async with client:
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
