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
    )


def validate_settings(settings: Settings) -> Optional[str]:
    if not settings.telegram_token:
        return "Не задано TELEGRAM_TOKEN"
    if not settings.client_id or not settings.client_secret:
        return "Не задано CLIENT_ID/CLIENT_SECRET"
    if not settings.sender_name:
        return "Не задано SENDER_NAME"
    return None
