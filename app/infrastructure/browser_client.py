from urllib.parse import urlsplit

from app.core.config import settings
from app.schemas.browser import (
    BrowserCookieItem,
    BrowserNetworkRequest,
    BrowserPageResult,
    CookieInteractionButton,
    CookieInteractionResult,
    CookieInteractionSnapshot,
)


class BrowserClient:
    max_stored_url_length = 500
    max_visible_text_length = 5000
    analytics_domains = ("mc.yandex.ru", "metrika.yandex.ru", "google-analytics.com", "googletagmanager.com")
    advertising_domains = ("doubleclick.net", "googleads.g.doubleclick.net", "googleadservices.com")
    accept_keywords = (
        "принять",
        "принимаю",
        "согласен",
        "согласиться",
        "accept",
        "agree",
        "allow",
        "ok",
        "хорошо",
    )
    reject_keywords = (
        "отклонить",
        "отказаться",
        "не принимаю",
        "reject",
        "decline",
        "deny",
        "refuse",
        "only necessary",
        "necessary only",
        "только необходимые",
    )
    settings_keywords = (
        "настроить",
        "настройки",
        "подробнее",
        "управление",
        "preferences",
        "settings",
        "customize",
        "manage",
    )
    unsafe_click_keywords = (
        "заказать",
        "купить",
        "отправить",
        "войти",
        "регистрация",
        "оплатить",
        "оставить заявку",
        "получить консультацию",
        "стать клиентом",
        "submit",
        "send",
        "order",
        "buy",
        "login",
        "sign in",
        "register",
        "pay",
    )

    def __init__(
        self,
        timeout_seconds: float | None = None,
        navigation_wait_until: str | None = None,
        max_network_requests: int | None = None,
        cookie_interaction_timeout_seconds: float | None = None,
        cookie_interaction_text_limit: int | None = None,
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
        self.cookie_interaction_timeout_seconds = (
            cookie_interaction_timeout_seconds
            if cookie_interaction_timeout_seconds is not None
            else settings.cookie_interaction_timeout_seconds
        )
        self.cookie_interaction_text_limit = (
            cookie_interaction_text_limit
            if cookie_interaction_text_limit is not None
            else settings.cookie_interaction_text_limit
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
                visible_text = await page.evaluate("document.body ? document.body.innerText : ''")
                cookies = await context.cookies()

                result = BrowserPageResult(
                    browser_check_performed=True,
                    url=url,
                    final_url=final_url,
                    title=title,
                    visible_text=visible_text[: self.max_visible_text_length],
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

    async def check_cookie_interaction(
        self,
        url: str,
        source_domain: str | None = None,
    ) -> CookieInteractionResult:
        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError:
            return CookieInteractionResult(
                enabled=True,
                performed=False,
                banner_found=False,
                reject_clicked=False,
                accept_clicked=False,
                warnings=[
                    "Playwright is not installed. Cookie interaction check was not performed."
                ],
            )

        browser = None
        source_domain = self._domain(source_domain or url)
        warnings: list[str] = []

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                reject_result = await self._interaction_scenario(
                    browser=browser,
                    url=url,
                    source_domain=source_domain,
                    action_type="reject",
                )
                accept_result = await self._interaction_scenario(
                    browser=browser,
                    url=url,
                    source_domain=source_domain,
                    action_type="accept",
                )
                await browser.close()
                browser = None

            buttons = self._dedupe_buttons(
                [*reject_result["buttons"], *accept_result["buttons"]]
            )
            initial_snapshot = reject_result["initial_snapshot"]
            after_reject_snapshot = reject_result["after_snapshot"]
            after_accept_snapshot = accept_result["after_snapshot"]
            reject_clicked = reject_result["clicked"]
            accept_clicked = accept_result["clicked"]
            reject_click_error = reject_result["click_error"]
            accept_click_error = accept_result["click_error"]
            warnings.extend(reject_result["warnings"])
            warnings.extend(accept_result["warnings"])

            cookies_reduced = self._reduced(
                initial_snapshot.cookies_count if initial_snapshot else None,
                after_reject_snapshot.cookies_count if after_reject_snapshot else None,
                reject_clicked,
            )
            analytics_reduced = self._reduced(
                initial_snapshot.analytics_requests_count if initial_snapshot else None,
                after_reject_snapshot.analytics_requests_count if after_reject_snapshot else None,
                reject_clicked,
            )
            advertising_reduced = self._reduced(
                initial_snapshot.advertising_requests_count if initial_snapshot else None,
                after_reject_snapshot.advertising_requests_count if after_reject_snapshot else None,
                reject_clicked,
            )

            if reject_clicked and (analytics_reduced is False or advertising_reduced is False):
                warnings.append(
                    "После нажатия кнопки отклонения количество cookies или сетевых запросов не уменьшилось; требуется ручная проверка."
                )

            return CookieInteractionResult(
                enabled=True,
                performed=True,
                banner_found=bool(buttons),
                buttons_found=buttons,
                reject_clicked=reject_clicked,
                accept_clicked=accept_clicked,
                reject_click_error=reject_click_error,
                accept_click_error=accept_click_error,
                initial_snapshot=initial_snapshot,
                after_reject_snapshot=after_reject_snapshot,
                after_accept_snapshot=after_accept_snapshot,
                cookies_reduced_after_reject=cookies_reduced,
                analytics_reduced_after_reject=analytics_reduced,
                advertising_reduced_after_reject=advertising_reduced,
                warnings=self._dedupe_text(warnings),
            )
        except (PlaywrightTimeoutError, PlaywrightError, Exception) as exc:
            return CookieInteractionResult(
                enabled=True,
                performed=False,
                banner_found=False,
                reject_clicked=False,
                accept_clicked=False,
                warnings=[f"Cookie interaction check failed: {type(exc).__name__}."],
            )
        finally:
            await self._safe_close(browser)

    async def _interaction_scenario(
        self,
        browser,
        url: str,
        source_domain: str | None,
        action_type: str,
    ) -> dict:
        context = None
        network_requests: list[BrowserNetworkRequest] = []
        warnings: list[str] = []
        clicked = False
        click_error = None
        after_snapshot = None

        try:
            context = await browser.new_context()
            page = await context.new_page()
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
                timeout=int(self.cookie_interaction_timeout_seconds * 1000),
            )
            buttons = await self._find_cookie_buttons(page)
            initial_snapshot = await self._interaction_snapshot(
                stage="initial",
                context=context,
                network_requests=network_requests,
                source_domain=source_domain,
            )
            button = self._best_button(buttons, action_type)
            if not button:
                warnings.append(f"Cookie {action_type} button was not found automatically.")
                return {
                    "buttons": buttons,
                    "initial_snapshot": initial_snapshot,
                    "after_snapshot": None,
                    "clicked": False,
                    "click_error": None,
                    "warnings": warnings,
                }

            network_requests.clear()
            try:
                await page.locator(button.selector or "").click(
                    timeout=int(self.cookie_interaction_timeout_seconds * 1000),
                    no_wait_after=True,
                )
                clicked = True
                await page.wait_for_timeout(1500)
            except Exception as exc:
                click_error = f"{type(exc).__name__}: {exc}"
                warnings.append(f"Cookie {action_type} click failed: {type(exc).__name__}.")

            after_snapshot = await self._interaction_snapshot(
                stage=f"after_{action_type}",
                context=context,
                network_requests=network_requests,
                source_domain=source_domain,
            )
            return {
                "buttons": buttons,
                "initial_snapshot": initial_snapshot,
                "after_snapshot": after_snapshot,
                "clicked": clicked,
                "click_error": click_error,
                "warnings": warnings,
            }
        finally:
            await self._safe_close(context)

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

    async def _find_cookie_buttons(self, page) -> list[CookieInteractionButton]:
        raw_buttons = await page.evaluate(
            """
            (textLimit) => {
              const elements = Array.from(document.querySelectorAll(
                'button, a, [role="button"], input[type="button"], input[type="submit"]'
              ));
              return elements.slice(0, 80).map((element, index) => {
                const label = (element.innerText || element.value || element.getAttribute('aria-label') || '').trim();
                const id = `cookie-check-${index}`;
                element.setAttribute('data-cookie-check-id', id);
                const rect = element.getBoundingClientRect();
                return {
                  label: label.slice(0, textLimit),
                  selector: `[data-cookie-check-id="${id}"]`,
                  visible: !!(rect.width && rect.height),
                  enabled: !element.disabled && element.getAttribute('aria-disabled') !== 'true'
                };
              });
            }
            """,
            self.cookie_interaction_text_limit,
        )

        buttons: list[CookieInteractionButton] = []
        for raw_button in raw_buttons:
            label = raw_button.get("label") or ""
            action_type = self._classify_cookie_button(label)
            if action_type is None:
                continue

            buttons.append(
                CookieInteractionButton(
                    label=label,
                    action_type=action_type,
                    selector=raw_button.get("selector"),
                    visible=bool(raw_button.get("visible")),
                    enabled=bool(raw_button.get("enabled")),
                )
            )

        return buttons

    def _classify_cookie_button(self, label: str) -> str | None:
        lowered = " ".join(label.lower().split())
        if not lowered:
            return None
        if any(keyword in lowered for keyword in self.unsafe_click_keywords):
            return None
        if any(keyword in lowered for keyword in self.reject_keywords):
            return "reject"
        if any(keyword in lowered for keyword in self.accept_keywords):
            return "accept"
        if any(keyword in lowered for keyword in self.settings_keywords):
            return "settings"
        return None

    def _best_button(
        self,
        buttons: list[CookieInteractionButton],
        action_type: str,
    ) -> CookieInteractionButton | None:
        candidates = [
            button
            for button in buttons
            if button.action_type == action_type and button.visible and button.enabled
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda button: len(button.label))[0]

    async def _interaction_snapshot(
        self,
        stage: str,
        context,
        network_requests: list[BrowserNetworkRequest],
        source_domain: str | None,
    ) -> CookieInteractionSnapshot:
        cookies = [self._to_cookie_item(cookie) for cookie in await context.cookies()]
        return CookieInteractionSnapshot(
            stage=stage,
            cookies=cookies,
            network_requests=network_requests[: self.max_network_requests],
            cookies_count=len(cookies),
            third_party_cookies_count=sum(
                1
                for cookie in cookies
                if self._is_third_party_domain(self._domain(cookie.domain), source_domain)
            ),
            analytics_requests_count=sum(
                1
                for request in network_requests
                if self._matches_domain(self._domain(request.domain), self.analytics_domains)
            ),
            advertising_requests_count=sum(
                1
                for request in network_requests
                if self._matches_domain(self._domain(request.domain), self.advertising_domains)
            ),
            third_party_requests_count=sum(1 for request in network_requests if request.is_third_party),
        )

    def _dedupe_buttons(
        self,
        buttons: list[CookieInteractionButton],
    ) -> list[CookieInteractionButton]:
        deduped: list[CookieInteractionButton] = []
        seen: set[tuple[str, str]] = set()
        for button in buttons:
            key = (button.label.lower(), button.action_type)
            if key in seen:
                continue

            seen.add(key)
            deduped.append(button)
        return deduped

    def _dedupe_text(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value or value in seen:
                continue

            seen.add(value)
            deduped.append(value)
        return deduped

    def _reduced(
        self,
        before: int | None,
        after: int | None,
        performed: bool,
    ) -> bool | None:
        if not performed or before is None or after is None:
            return None
        return after < before

    def _matches_domain(self, domain: str | None, candidates: tuple[str, ...]) -> bool:
        if not domain:
            return False
        return any(domain == candidate or domain.endswith(f".{candidate}") for candidate in candidates)

    def _is_third_party_domain(self, domain: str | None, source_domain: str | None) -> bool:
        if not domain or not source_domain:
            return False
        return domain != source_domain and not domain.endswith(f".{source_domain}")

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
        return parsed.hostname.lower().strip(".") if parsed.hostname else None
