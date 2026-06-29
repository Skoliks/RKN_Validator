from typing import Protocol

from app.core.config import settings
from app.infrastructure.browser_client import BrowserClient
from app.schemas.browser import BrowserCheckResult, BrowserPageResult, CookieInteractionResult
from app.schemas.pages import PageData


class BrowserPageClient(Protocol):
    async def check_page(self, url: str, source_domain: str | None = None) -> BrowserPageResult:
        ...

    async def check_cookie_interaction(
        self,
        url: str,
        source_domain: str | None = None,
    ) -> CookieInteractionResult:
        ...


class BrowserCheckService:
    cookie_interaction_not_found_warning = (
        "Cookie-баннер или кнопка отклонения не были найдены автоматически."
    )

    def __init__(
        self,
        browser_client: BrowserPageClient | None = None,
        enabled: bool | None = None,
        cookie_interaction_enabled: bool | None = None,
        max_pages: int = 1,
        max_network_requests: int | None = None,
    ) -> None:
        self.browser_client = browser_client or BrowserClient()
        self.enabled = settings.enable_browser_check if enabled is None else enabled
        self.cookie_interaction_enabled = (
            settings.enable_cookie_interaction_check
            if cookie_interaction_enabled is None
            else cookie_interaction_enabled
        )
        self.max_pages = max_pages
        self.max_network_requests = (
            max_network_requests
            if max_network_requests is not None
            else settings.browser_max_network_requests
        )

    async def check(
        self,
        pages_or_urls: list[PageData] | list[str],
        source_domain: str | None = None,
    ) -> BrowserCheckResult:
        if not self.enabled:
            return BrowserCheckResult(enabled=False, performed=False, pages_checked=0)

        urls = self._extract_urls(pages_or_urls)[: self.max_pages]
        if not urls:
            return BrowserCheckResult(
                enabled=True,
                performed=False,
                pages_checked=0,
                warnings=["No URLs were provided for browser check."],
            )

        items: list[BrowserPageResult] = []
        for url in urls:
            page_result = await self.browser_client.check_page(url, source_domain=source_domain)
            items.append(self._limit_network_requests(page_result))

        cookie_interaction = None
        if self.cookie_interaction_enabled:
            try:
                cookie_interaction = await self.browser_client.check_cookie_interaction(
                    urls[0],
                    source_domain=source_domain,
                )
            except Exception as exc:
                cookie_interaction = self._cookie_interaction_error_result(exc)
            else:
                cookie_interaction = self._normalize_cookie_interaction_result(
                    cookie_interaction
                )

        return BrowserCheckResult(
            enabled=True,
            performed=any(item.browser_check_performed for item in items),
            pages_checked=len(items),
            items=items,
            cookie_interaction=cookie_interaction,
            warnings=[
                item.message
                for item in items
                if item.error_type and item.message
            ],
        )

    def _extract_urls(self, pages_or_urls: list[PageData] | list[str]) -> list[str]:
        urls: list[str] = []
        for item in pages_or_urls:
            if isinstance(item, str):
                urls.append(item)
            else:
                urls.append(item.final_url or item.url)
        return urls

    def _limit_network_requests(self, page_result: BrowserPageResult) -> BrowserPageResult:
        if len(page_result.network_requests) <= self.max_network_requests:
            return page_result

        return page_result.model_copy(
            update={
                "network_requests": page_result.network_requests[: self.max_network_requests],
                "warnings": [
                    *page_result.warnings,
                    "Network request list was truncated by browser check settings.",
                ],
            }
        )

    def _cookie_interaction_error_result(self, exc: Exception) -> CookieInteractionResult:
        return CookieInteractionResult(
            enabled=True,
            performed=True,
            banner_found=False,
            buttons_found=[],
            reject_clicked=False,
            accept_clicked=False,
            warnings=[
                self.cookie_interaction_not_found_warning,
                f"Cookie interaction check failed: {type(exc).__name__}.",
            ],
        )

    def _normalize_cookie_interaction_result(
        self,
        result: CookieInteractionResult,
    ) -> CookieInteractionResult:
        if result.performed:
            if not result.banner_found and not result.buttons_found:
                return result.model_copy(
                    update={
                        "warnings": self._with_cookie_interaction_not_found_warning(
                            result.warnings
                        )
                    }
                )
            return result

        if self._has_timeout_warning(result.warnings):
            return result.model_copy(
                update={
                    "performed": True,
                    "banner_found": False,
                    "buttons_found": [],
                    "reject_clicked": False,
                    "accept_clicked": False,
                    "warnings": self._with_cookie_interaction_not_found_warning(
                        result.warnings
                    ),
                }
            )

        return result

    def _has_timeout_warning(self, warnings: list[str]) -> bool:
        return any(
            "TimeoutError" in warning or "timeout" in warning.lower()
            for warning in warnings
        )

    def _with_cookie_interaction_not_found_warning(
        self,
        warnings: list[str],
    ) -> list[str]:
        deduped: list[str] = []
        for warning in [self.cookie_interaction_not_found_warning, *warnings]:
            if warning and warning not in deduped:
                deduped.append(warning)
        return deduped
