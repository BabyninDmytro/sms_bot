import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

TRUE_VALUES = {"1", "true", "yes", "on"}

load_dotenv()

@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    telegram_token: str
    sender_name: str
    use_sandbox: bool
    max_sms_text_length: int
    max_sms_segments: int
    telethon_api_id: int
    telethon_api_hash: str
    telethon_session_name: str
    telethon_watch_chats: tuple[str, ...]
    telethon_keywords: tuple[str, ...]
    telethon_alert_phones: tuple[str, ...]
    telethon_dedupe_seconds: int
    telethon_max_sms_chars: int

    @property
    def auth_url(self) -> str:
        return "https://api-gateway.kyivstar.ua/idp/oauth2/token"

    @property
    def sms_url(self) -> str:
        if self.use_sandbox:
            return "https://api-gateway.kyivstar.ua/sandbox/rest/v1beta/sms"
        return "https://api-gateway.kyivstar.ua/rest/v1/sms"


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _parse_int(value: str, default: int) -> int:
    try:
        parsed = int((value or "").strip())
        if parsed > 0:
            return parsed
    except ValueError:
        pass
    return default


def _parse_optional_int(value: str, default: int = 0) -> int:
    try:
        return int((value or "").strip())
    except ValueError:
        return default


def _parse_csv_list(value: str) -> tuple[str, ...]:
    if not value:
        return tuple()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_int_range(value: str, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int((value or "").strip())
        if min_value <= parsed <= max_value:
            return parsed
    except ValueError:
        pass
    return default


def load_settings() -> Settings:
    return Settings(
        client_id=os.getenv("CLIENT_ID", "").strip(),
        client_secret=os.getenv("CLIENT_SECRET", "").strip(),
        telegram_token=os.getenv("TELEGRAM_TOKEN", "").strip(),
        sender_name=os.getenv("SENDER_NAME", "messagedesk").strip(),
        use_sandbox=_parse_bool(os.getenv("USE_SANDBOX", "true"), default=True),
        max_sms_text_length=_parse_int(os.getenv("MAX_SMS_TEXT_LENGTH", ""), default=255),
        max_sms_segments=_parse_int_range(os.getenv("MAX_SMS_SEGMENTS", ""), default=6, min_value=1, max_value=6),
        telethon_api_id=_parse_optional_int(os.getenv("TELETHON_API_ID", "0"), default=0),
        telethon_api_hash=os.getenv("TELETHON_API_HASH", "").strip(),
        telethon_session_name=os.getenv("TELETHON_SESSION_NAME", "telethon_sms_listener").strip(),
        telethon_watch_chats=_parse_csv_list(os.getenv("TELETHON_WATCH_CHATS", "")),
        telethon_keywords=tuple(
            keyword.lower() for keyword in _parse_csv_list(os.getenv("TELETHON_KEYWORDS", ""))
        ),
        telethon_alert_phones=_parse_csv_list(os.getenv("TELETHON_ALERT_PHONES", "")),
        telethon_dedupe_seconds=_parse_int(os.getenv("TELETHON_DEDUPE_SECONDS", "1800"), default=1800),
        telethon_max_sms_chars=_parse_int_range(
            os.getenv("TELETHON_MAX_SMS_CHARS", "180"),
            default=180,
            min_value=40,
            max_value=255,
        ),
    )


def validate_settings(settings: Settings) -> Optional[str]:
    if not settings.telegram_token:
        return "Не задано TELEGRAM_TOKEN"
    if not settings.client_id or not settings.client_secret:
        return "Не задано CLIENT_ID/CLIENT_SECRET"
    if not settings.sender_name:
        return "Не задано SENDER_NAME"
    return None
