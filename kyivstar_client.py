import base64
import logging
import time
from typing import Optional, Tuple

import aiohttp
from aiohttp import ClientConnectionError, ClientError, ClientResponse

from config import Settings

TOKEN_SAFETY_MARGIN_SECONDS = 60
DEFAULT_TOKEN_TTL_SECONDS = 8 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 10

logger = logging.getLogger(__name__)


def _log(level: int, cid: str, message: str) -> None:
    logger.log(level, "[cid=%s] %s", cid, message)


class KyivstarClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._cached_access_token: Optional[str] = None
        self._cached_token_expiry_ts: float = 0.0
        self._session: Optional[aiohttp.ClientSession] = None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def invalidate_token_cache(self) -> None:
        self._cached_access_token = None
        self._cached_token_expiry_ts = 0.0

    def _build_basic_auth_header(self) -> str:
        auth_str = f"{self.settings.client_id}:{self.settings.client_secret}"
        auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        return f"Basic {auth_base64}"

    async def get_token(self, cid: str, force_refresh: bool = False) -> Optional[str]:
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

        session = await self._get_session()

        try:
            async with session.post(self.settings.auth_url, headers=headers, data=data) as response:
                _log(logging.INFO, cid, f"Auth status={response.status}")
                response.raise_for_status()

                body = await response.json()
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

        except TimeoutError:
            _log(logging.ERROR, cid, "Auth timeout під час запиту токена")
        except ClientConnectionError:
            _log(logging.ERROR, cid, "Auth connection error під час запиту токена")
        except aiohttp.ClientResponseError as exc:
            _log(logging.ERROR, cid, f"Auth HTTP error status={exc.status}")
        except ClientError as exc:
            _log(logging.ERROR, cid, f"Auth request exception: {exc}")

        return None

    async def send_sms(self, cid: str, token: str, phone: str, text: str, max_segments: int) -> Tuple[Optional[ClientResponse], str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": self.settings.sender_name,
            "to": phone,
            "text": text,
            "maxSegments": max_segments,
        }

        session = await self._get_session()

        try:
            async with session.post(self.settings.sms_url, json=payload, headers=headers) as response:
                _log(logging.INFO, cid, f"SMS status={response.status}")
                return response, await response.text()
        except TimeoutError:
            return None, "Timeout при зверненні до SMS API"
        except ClientConnectionError:
            return None, "Немає з'єднання з SMS API"
        except ClientError as exc:
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
