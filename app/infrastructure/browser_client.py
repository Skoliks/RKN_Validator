from urllib.parse import urlsplit

from app.core.config import settings
from app.schemas.browser import BrowserCookieItem, BrowserNetworkRequest, BrowserPageResult


class BrowserClient:
    max_stored_url_length = 500

    def __init__(
        self,
        timeout_seconds: float | None = None,
        navigation_wait_until: str | None = None,
        max_network_requests: int | None = None,
    ) -> None:
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.browser_timeout_seconds
        )
        self.navigation_wait_until = navigation_wait_until or settings.browser_navigation_wait_until
        self.max_network_requests = (
            max_network_requests
            if max_network_requests is not None
            else settings.browser_max_network_requests
        )

    async def check_page(self, url: str, source_domain: str | None = None) -> BrowserPageResult:
        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError:
            return self._error_result(
                url=url,
                error_type="browser_not_installed",
                message=(
                    "Playwright is not installed. Install it with 'pip install playwright' "
                    "and then run 'python -m playwright install chromium'."
                ),
            )

        browser = None
        context = None
        network_requests: list[BrowserNetworkRequest] = []
        console_errors: list[str] = []
        source_domain = self._domain(source_domain or url)

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                page.on(
                    "console",
                    lambda message: console_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on(
                    "response",
                    lambda response: self._capture_response(
                        response=response,
                        source_domain=source_domain,
                        network_requests=network_requests,
                    ),
                )

                await page.goto(
                    url,
                    wait_until=self.navigation_wait_until,
                    timeout=int(self.timeout_seconds * 1000),
                )
                title = await page.title()
                final_url = page.url
                cookies = await context.cookies()

                result = BrowserPageResult(
                    browser_check_performed=True,
                    url=url,
                    final_url=final_url,
                    title=title,
                    cookies_after_load=[self._to_cookie_item(cookie) for cookie in cookies],
                    network_requests=network_requests[: self.max_network_requests],
                    console_errors=console_errors,
                    error_type=None,
                    message=None,
                    warnings=[],
                )
                await context.close()
                context = None
                await browser.close()
                browser = None
                return result
        except PlaywrightTimeoutError as exc:
            return self._error_result(url=url, error_type="timeout", message=str(exc))
        except PlaywrightError as exc:
            message = str(exc)
            error_type = (
                "browser_not_installed"
                if "Executable doesn't exist" in message or "playwright install" in message
                else "navigation_error"
            )
            return self._error_result(url=url, error_type=error_type, message=message)
        except Exception as exc:
            return self._error_result(url=url, error_type="unknown_error", message=str(exc))
        finally:
            await self._safe_close(context)
            await self._safe_close(browser)

    def _capture_response(
        self,
        response,
        source_domain: str | None,
        network_requests: list[BrowserNetworkRequest],
    ) -> None:
        if len(network_requests) >= self.max_network_requests:
            return

        request = response.request
        domain = self._domain(response.url)
        normalized_url, path, has_query, original_url_truncated = self._normalize_network_url(
            response.url
        )
        network_requests.append(
            BrowserNetworkRequest(
                url=normalized_url,
                path=path,
                has_query=has_query,
                original_url_truncated=original_url_truncated,
                method=request.method,
                resource_type=request.resource_type,
                status_code=response.status,
                domain=domain,
                is_third_party=bool(source_domain and domain and domain != source_domain),
            )
        )

    def _normalize_network_url(self, url: str) -> tuple[str, str | None, bool, bool]:
        parsed = urlsplit(url)
        path = parsed.path or None
        has_query = bool(parsed.query)

        if parsed.scheme and parsed.netloc:
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        else:
            normalized = url.split("?", 1)[0]

        original_url_truncated = normalized != url
        if len(normalized) > self.max_stored_url_length:
            normalized = normalized[: self.max_stored_url_length]
            original_url_truncated = True

        return normalized, path, has_query, original_url_truncated

    def _to_cookie_item(self, cookie: dict) -> BrowserCookieItem:
        return BrowserCookieItem(
            name=cookie.get("name", ""),
            domain=cookie.get("domain"),
            path=cookie.get("path"),
            http_only=cookie.get("httpOnly"),
            secure=cookie.get("secure"),
            same_site=cookie.get("sameSite"),
        )

    async def _safe_close(self, resource) -> None:
        if resource is None:
            return

        try:
            await resource.close()
        except Exception:
            return

    def _error_result(self, url: str, error_type: str, message: str) -> BrowserPageResult:
        return BrowserPageResult(
            browser_check_performed=False,
            url=url,
            error_type=error_type,
            message=message,
            warnings=[message],
        )

    def _domain(self, value: str | None) -> str | None:
        if not value:
            return None

        parsed = urlsplit(value if "://" in value else f"https://{value}")
        return parsed.hostname.lower().rstrip(".") if parsed.hostname else None
