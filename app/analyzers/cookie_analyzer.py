from app.schemas.browser import BrowserCheckResult, BrowserPageResult
from app.schemas.cookies import (
    CookieAnalysisResult,
    CookieBannerCandidate,
    CookieBeforeConsentItem,
    CookieNetworkRequestItem,
)


class CookieAnalyzer:
    analytics_cookie_names = {
        "_ym_uid",
        "_ym_d",
        "_ym_isad",
        "_ym_visorc",
        "yabs-sid",
        "yandexuid",
        "yuidss",
        "ymex",
    }
    technical_cookie_markers = ("session", "csrf", "xsrf", "phpsessid", "jsessionid", "plp")

    analytics_domains = ("mc.yandex.ru", "metrika.yandex.ru", "google-analytics.com", "googletagmanager.com")
    advertising_domains = ("doubleclick.net", "googleads.g.doubleclick.net", "googleadservices.com")
    video_domains = ("youtube.com", "ytimg.com", "googlevideo.com")
    fonts_domains = ("fonts.gstatic.com", "fonts.googleapis.com")
    cdn_domains = ("unpkg.com", "cdn.jsdelivr.net", "cdnjs.cloudflare.com")
    social_domains = ("facebook.com", "instagram.com", "vk.com")

    banner_markers = (
        "cookie",
        "cookies",
        "куки",
        "cookie-файлы",
        "файлы cookie",
        "согласие",
        "персональные данные",
    )
    accept_markers = ("принять", "согласен", "accept", "allow")
    reject_markers = ("отклонить", "отказаться", "reject", "decline")
    settings_markers = ("настроить", "настройки", "settings", "preferences")

    def analyze(self, browser_check: BrowserCheckResult | None) -> CookieAnalysisResult:
        if not browser_check or not browser_check.performed or not browser_check.items:
            return CookieAnalysisResult(
                browser_check_available=False,
                analyzed=False,
                warnings=[
                    "Браузерная проверка не выполнялась, поэтому cookie-поведение не анализировалось."
                ],
                message="Браузерная проверка недоступна.",
            )

        cookies: list[CookieBeforeConsentItem] = []
        requests: list[CookieNetworkRequestItem] = []
        banner_candidates: list[CookieBannerCandidate] = []
        warnings: list[str] = []
        visible_text_seen = False

        for page in browser_check.items:
            if not page.browser_check_performed:
                continue

            cookies.extend(self._cookies_for_page(page))
            requests.extend(self._requests_for_page(page))

            if page.visible_text:
                visible_text_seen = True
                candidate = self._banner_candidate(page)
                if candidate:
                    banner_candidates.append(candidate)

        if not visible_text_seen:
            warnings.append(
                "Видимый текст страницы не был передан из браузерной проверки, поэтому наличие cookie-баннера не анализировалось."
            )

        requests = self._dedupe_requests(requests)
        banner_found = bool(banner_candidates)
        accept_found = any(candidate.accept_found for candidate in banner_candidates)
        reject_found = any(candidate.reject_found for candidate in banner_candidates)
        settings_found = any(candidate.settings_found for candidate in banner_candidates)
        cookies_found = bool(cookies)
        third_party_cookies_found = any(item.is_third_party for item in cookies)
        analytics_requests_found = any(item.category == "analytics" for item in requests)
        advertising_requests_found = any(item.category == "advertising" for item in requests)
        third_party_requests_found = bool(requests)

        self._append_result_warnings(
            warnings=warnings,
            cookies_found=cookies_found,
            third_party_cookies_found=third_party_cookies_found,
            analytics_requests_found=analytics_requests_found,
            advertising_requests_found=advertising_requests_found,
            banner_found=banner_found,
            reject_found=reject_found,
        )

        return CookieAnalysisResult(
            browser_check_available=True,
            analyzed=True,
            banner_found=banner_found,
            accept_button_found=accept_found,
            reject_button_found=reject_found,
            settings_button_found=settings_found,
            cookies_before_consent_found=cookies_found,
            third_party_cookies_before_consent_found=third_party_cookies_found,
            analytics_requests_before_consent_found=analytics_requests_found,
            advertising_requests_before_consent_found=advertising_requests_found,
            third_party_requests_before_consent_found=third_party_requests_found,
            banner_candidates=banner_candidates,
            cookies_before_consent=cookies,
            requests_before_consent=requests,
            warnings=warnings,
            message="Cookie-поведение проанализировано по данным браузерной проверки.",
        )

    def _cookies_for_page(self, page: BrowserPageResult) -> list[CookieBeforeConsentItem]:
        items: list[CookieBeforeConsentItem] = []
        page_domain = self._normalize_domain(page.final_url or page.url)
        for cookie in page.cookies_after_load:
            domain = self._normalize_domain(cookie.domain)
            items.append(
                CookieBeforeConsentItem(
                    name=cookie.name,
                    domain=cookie.domain,
                    is_third_party=self._is_third_party(domain, page_domain),
                    category=self._cookie_category(cookie.name, domain),
                )
            )
        return items

    def _requests_for_page(self, page: BrowserPageResult) -> list[CookieNetworkRequestItem]:
        items: list[CookieNetworkRequestItem] = []
        for request in page.network_requests:
            if not request.is_third_party:
                continue

            items.append(
                CookieNetworkRequestItem(
                    url=request.url,
                    path=request.path,
                    domain=request.domain,
                    resource_type=request.resource_type,
                    category=self._request_category(self._normalize_domain(request.domain)),
                    is_third_party=request.is_third_party,
                )
            )
        return items

    def _dedupe_requests(
        self,
        requests: list[CookieNetworkRequestItem],
    ) -> list[CookieNetworkRequestItem]:
        deduped: list[CookieNetworkRequestItem] = []
        seen: set[tuple[str | None, str, str | None, str]] = set()
        for item in requests:
            key = (
                item.domain,
                item.path or item.url,
                item.resource_type,
                item.category,
            )
            if key in seen:
                continue

            seen.add(key)
            deduped.append(item)
        return deduped

    def _banner_candidate(self, page: BrowserPageResult) -> CookieBannerCandidate | None:
        text = (page.visible_text or "").strip()
        lowered = text.lower()
        if not any(marker in lowered for marker in self.banner_markers):
            return None

        evidence = self._evidence(text)
        return CookieBannerCandidate(
            page_url=page.final_url or page.url,
            text=evidence,
            accept_found=any(marker in lowered for marker in self.accept_markers),
            reject_found=any(marker in lowered for marker in self.reject_markers),
            settings_found=any(marker in lowered for marker in self.settings_markers),
            evidence=evidence,
        )

    def _cookie_category(self, name: str, domain: str | None) -> str:
        normalized_name = name.lower()
        if normalized_name in self.analytics_cookie_names or self._matches_domain(domain, ("yandex.ru", "mc.yandex.ru")):
            return "analytics"
        if self._matches_domain(domain, self.advertising_domains):
            return "advertising"
        if self._matches_domain(domain, self.video_domains):
            return "video"
        if self._matches_domain(domain, self.social_domains):
            return "social"
        if any(marker in normalized_name for marker in self.technical_cookie_markers):
            return "technical"
        return "unknown"

    def _request_category(self, domain: str | None) -> str:
        if self._matches_domain(domain, self.analytics_domains):
            return "analytics"
        if self._matches_domain(domain, self.advertising_domains):
            return "advertising"
        if self._matches_domain(domain, self.video_domains):
            return "video"
        if self._matches_domain(domain, self.fonts_domains):
            return "fonts"
        if self._matches_domain(domain, self.cdn_domains):
            return "cdn"
        if self._matches_domain(domain, self.social_domains):
            return "social"
        return "unknown"

    def _append_result_warnings(
        self,
        warnings: list[str],
        cookies_found: bool,
        third_party_cookies_found: bool,
        analytics_requests_found: bool,
        advertising_requests_found: bool,
        banner_found: bool,
        reject_found: bool,
    ) -> None:
        if cookies_found:
            warnings.append(
                "На момент браузерной проверки обнаружены cookies после первичной загрузки страницы до явного выбора пользователя."
            )
        if third_party_cookies_found:
            warnings.append("Обнаружены cookies сторонних доменов до явного выбора пользователя.")
        if analytics_requests_found:
            warnings.append("Обнаружены запросы к аналитическим сервисам до явного выбора пользователя.")
        if advertising_requests_found:
            warnings.append("Обнаружены запросы к рекламным сервисам до явного выбора пользователя.")
        if banner_found and not reject_found:
            warnings.append("Найден cookie-баннер, но не найдена явная кнопка отклонения.")
        if not banner_found:
            warnings.append("На момент браузерной проверки cookie-баннер не найден или не был распознан автоматически.")

    def _matches_domain(self, domain: str | None, candidates: tuple[str, ...]) -> bool:
        if not domain:
            return False
        return any(domain == candidate or domain.endswith(f".{candidate}") for candidate in candidates)

    def _normalize_domain(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().lower().lstrip(".")
        if "://" in normalized:
            from urllib.parse import urlsplit

            parsed = urlsplit(normalized)
            normalized = parsed.hostname or normalized
        return normalized.rstrip(".")

    def _is_third_party(self, domain: str | None, page_domain: str | None) -> bool:
        if not domain or not page_domain:
            return False
        return domain != page_domain and not domain.endswith(f".{page_domain}")

    def _evidence(self, text: str) -> str:
        compact = " ".join(text.split())
        return compact[:500]
