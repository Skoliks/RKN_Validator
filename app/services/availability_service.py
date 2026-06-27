import ssl

import httpx

from app.infrastructure.http_client import HttpClient
from app.schemas.availability import AvailabilityInfo
from app.schemas.site import SiteInfo


UNAVAILABLE_MESSAGE = "Сайт недоступен, поэтому проверку выполнить не удалось."


class AvailabilityService:
    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http_client = http_client or HttpClient()

    async def check(self, site: SiteInfo) -> AvailabilityInfo:
        try:
            response = await self.http_client.get(site.normalized_url)
        except httpx.TimeoutException:
            return self._unavailable("timeout")
        except httpx.TooManyRedirects:
            return self._unavailable("too_many_redirects")
        except httpx.ConnectError as exc:
            return self._unavailable(self._classify_connect_error(exc))
        except httpx.HTTPError:
            return self._unavailable("site_unavailable")
        except Exception:
            return self._unavailable("unknown_error")

        if 200 <= response.status_code < 400:
            return AvailabilityInfo(
                available=True,
                status_code=response.status_code,
                message="Сайт доступен.",
            )

        return self._unavailable(
            "site_unavailable",
            status_code=response.status_code,
        )

    def _unavailable(self, error_type: str, status_code: int | None = None) -> AvailabilityInfo:
        return AvailabilityInfo(
            available=False,
            status_code=status_code,
            error_type=error_type,
            message=UNAVAILABLE_MESSAGE,
        )

    def _classify_connect_error(self, exc: httpx.ConnectError) -> str:
        if self._has_ssl_error(exc):
            return "ssl_error"

        message = str(exc).lower()
        dns_markers = (
            "name or service not known",
            "nodename nor servname provided",
            "getaddrinfo failed",
            "temporary failure in name resolution",
            "no such host",
        )
        if any(marker in message for marker in dns_markers):
            return "dns_error"

        return "site_unavailable"

    def _has_ssl_error(self, exc: BaseException) -> bool:
        current: BaseException | None = exc
        while current is not None:
            if isinstance(current, ssl.SSLError):
                return True
            current = current.__cause__ or current.__context__
        return False
