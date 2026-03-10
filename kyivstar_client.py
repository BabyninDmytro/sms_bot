import base64
import logging
import time
from typing import Optional, Tuple

import requests
from requests import Response
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, RequestException, Timeout

from config import Settings

TOKEN_SAFETY_MARGIN_SECONDS = 60
DEFAULT_TOKEN_TTL_SECONDS = 8 * 60 * 60

logger = logging.getLogger(__name__)


def _log(level: int, cid: str, message: str) -> None:
    logger.log(level, "[cid=%s] %s", cid, message)


class KyivstarClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._cached_access_token: Optional[str] = None
        self._cached_token_expiry_ts: float = 0.0

    def invalidate_token_cache(self) -> None:
        self._cached_access_token = None
        self._cached_token_expiry_ts = 0.0

    def _build_basic_auth_header(self) -> str:
        auth_str = f"{self.settings.client_id}:{self.settings.client_secret}"
        auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        return f"Basic {auth_base64}"

    def get_token(self, cid: str, force_refresh: bool = False) -> Optional[str]:
        now = time.time()
        if (
            not force_refresh
            and self._cached_access_token
            and now < (self._cached_token_expiry_ts - TOKEN_SAFETY_MARGIN_SECONDS)
        ):
            _log(logging.INFO, cid, "Використано токен з кеша")
            return self._cached_access_token

        headers = {
            "Authorization": self._build_basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}

        try:
            response = requests.post(self.settings.auth_url, headers=headers, data=data, timeout=10)
            _log(logging.INFO, cid, f"Auth status={response.status_code}")
            response.raise_for_status()

            body = response.json()
            access_token = body.get("access_token")
            expires_raw = body.get("expires_in", DEFAULT_TOKEN_TTL_SECONDS)
            try:
                expires_in = int(expires_raw)
                if expires_in <= 0:
                    expires_in = DEFAULT_TOKEN_TTL_SECONDS
            except (TypeError, ValueError):
                expires_in = DEFAULT_TOKEN_TTL_SECONDS

            if not access_token:
                _log(logging.ERROR, cid, "Auth error: access_token відсутній у відповіді")
                return None

            self._cached_access_token = access_token
            self._cached_token_expiry_ts = now + expires_in
            _log(logging.INFO, cid, f"Отримано новий токен, ttl={expires_in}s")
            return access_token

        except Timeout:
            _log(logging.ERROR, cid, "Auth timeout під час запиту токена")
        except RequestsConnectionError:
            _log(logging.ERROR, cid, "Auth connection error під час запиту токена")
        except HTTPError:
            status = response.status_code if 'response' in locals() else 'unknown'
            _log(logging.ERROR, cid, f"Auth HTTP error status={status}")
        except RequestException as exc:
            _log(logging.ERROR, cid, f"Auth request exception: {exc}")

        return None

    def send_sms(self, cid: str, token: str, phone: str, text: str) -> Tuple[Optional[Response], str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": self.settings.sender_name,
            "to": phone,
            "text": text,
        }

        try:
            response = requests.post(self.settings.sms_url, json=payload, headers=headers, timeout=10)
            _log(logging.INFO, cid, f"SMS status={response.status_code}")
            return response, response.text
        except Timeout:
            return None, "Timeout при зверненні до SMS API"
        except RequestsConnectionError:
            return None, "Немає з'єднання з SMS API"
        except RequestException as exc:
            return None, f"Помилка запиту до SMS API: {exc}"


def map_error_message(status_code: Optional[int], response_text: str) -> str:
    if status_code == 400:
        return f"400 Bad Request: Некоректні параметри запиту. {response_text}"
    if status_code == 401:
        return f"401 Unauthorized: Невірний/протермінований токен або Client credentials. {response_text}"
    if status_code == 403:
        return f"403 Forbidden: Немає доступу до запитуваного ресурсу. {response_text}"
    if status_code == 413:
        return f"413 Payload Too Large: Повідомлення завелике для відправки. Скоротіть текст SMS. {response_text}"
    if status_code == 422:
        return f"422 Unprocessable Entity: Дані запиту не пройшли валідацію (номер/параметри/text). {response_text}"
    if status_code == 500:
        return f"500 Internal Server Error: Проблема на стороні сервера провайдера. {response_text}"
    return response_text
