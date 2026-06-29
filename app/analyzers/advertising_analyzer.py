import re
from html import unescape
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.advertising import (
    AdvertisingAnalysisResult,
    AdvertisingServiceItem,
    AdvertisingTextItem,
)
from app.schemas.browser import BrowserCheckResult
from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.pages import PageData


class AdvertisingAnalyzer:
    service_signatures = (
        ("doubleclick.net", "advertising", "Google DoubleClick"),
        ("googlesyndication.com", "advertising", "Google Ads"),
        ("googleadservices.com", "advertising", "Google Ads"),
        ("an.yandex.ru", "advertising", "Yandex Ads"),
        ("yabs.yandex.ru", "advertising", "Yandex Ads"),
        ("yandexadexchange.net", "advertising", "Yandex Ads"),
        ("ads.vk.com", "social_ads", "VK Ads"),
        ("vk.com/rtrg", "social_ads", "VK Ads"),
        ("top-fwz1.mail.ru", "advertising", "MyTarget / Mail.ru"),
        ("target.my.com", "advertising", "MyTarget / Mail.ru"),
        ("mytarget", "advertising", "MyTarget"),
        ("facebook.com/tr", "social_ads", "Meta Ads"),
        ("connect.facebook.net", "social_ads", "Meta Ads"),
        ("fbq", "social_ads", "Meta Ads"),
        ("analytics.tiktok.com", "social_ads", "TikTok Ads"),
        ("business-api.tiktok.com", "social_ads", "TikTok Ads"),
    )
    html_url_selectors = (
        ("script", "src"),
        ("link", "href"),
        ("iframe", "src"),
        ("img", "src"),
        ("a", "href"),
    )
    fallback_url_pattern = re.compile(
        r"\b(?:src|href)\s*=\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )
    erid_patterns = (
        re.compile(r"(?i)\berid\b"),
        re.compile(r"(?i)erid[:= ]+[a-zа-яё0-9._-]{6,}"),
    )
    ad_label_pattern = re.compile(r"(?iu)(?<![а-яёa-z])(?:реклама|advertisement)(?![а-яёa-z])")
    advertiser_pattern = re.compile(r"(?iu)(?<![а-яёa-z])рекламодатель(?![а-яёa-z])")
    sponsored_pattern = re.compile(r"(?iu)(?<![а-яёa-z])(?:спонсорский|sponsored)(?![а-яёa-z])")
    possible_ad_tokens = {
        "ad",
        "ads",
        "advert",
        "banner",
        "promo",
        "sponsored",
        "ya-direct",
        "google-ad",
        "adsbygoogle",
    }

    def analyze(
        self,
        pages: list[PageData] | None = None,
        external_services: ExternalServicesResult | None = None,
        browser_check: BrowserCheckResult | None = None,
    ) -> AdvertisingAnalysisResult:
        services: list[AdvertisingServiceItem] = []
        text_items: list[AdvertisingTextItem] = []
        seen_services: set[tuple[str, str, str | None]] = set()
        seen_text: set[tuple[str, str, str]] = set()

        for page in pages or []:
            page_url = page.final_url or page.url
            html = page.html or ""
            text = self._page_text(page)

            self._collect_html_services(html, page_url, services, seen_services)
            self._collect_text_items(text, html, page_url, text_items, seen_text)
            self._collect_possible_ad_blocks(html, page_url, text_items, seen_text)

        self._collect_external_services(external_services, services, seen_services)
        self._collect_browser_services(browser_check, services, seen_services)

        ad_services_found = bool(services)
        erid_found = any(item.item_type == "erid" for item in text_items)
        ad_marking_found = any(item.item_type == "ad_label" for item in text_items)
        advertiser_info_found = any(item.item_type == "advertiser_info" for item in text_items)
        possible_ad_blocks_found = any(
            item.item_type == "possible_ad_block" for item in text_items
        )
        found = (
            ad_services_found
            or erid_found
            or ad_marking_found
            or advertiser_info_found
            or possible_ad_blocks_found
            or any(item.item_type == "sponsored_text" for item in text_items)
        )

        return AdvertisingAnalysisResult(
            found=found,
            ad_services_found=ad_services_found,
            ad_marking_found=ad_marking_found,
            erid_found=erid_found,
            advertiser_info_found=advertiser_info_found,
            possible_ad_blocks_found=possible_ad_blocks_found,
            services=services,
            text_items=text_items,
            warnings=self._warnings(
                found=found,
                ad_services_found=ad_services_found,
                erid_found=erid_found,
                ad_marking_found=ad_marking_found,
                possible_ad_blocks_found=possible_ad_blocks_found,
            ),
        )

    def _collect_html_services(
        self,
        html: str,
        page_url: str,
        services: list[AdvertisingServiceItem],
        seen: set[tuple[str, str, str | None]],
    ) -> None:
        if not html:
            return

        soup = BeautifulSoup(html, "html.parser")
        for tag_name, attr_name in self.html_url_selectors:
            for tag in soup.find_all(tag_name):
                if not isinstance(tag, Tag):
                    continue

                raw_url = tag.get(attr_name)
                if not isinstance(raw_url, str):
                    continue
                self._add_service(
                    url=self._normalize_url(urljoin(page_url, raw_url)),
                    page_url=page_url,
                    source="html",
                    services=services,
                    seen=seen,
                )

        for match in self.fallback_url_pattern.finditer(html):
            self._add_service(
                url=self._normalize_url(urljoin(page_url, match.group(1).strip())),
                page_url=page_url,
                source="html",
                services=services,
                seen=seen,
            )

    def _collect_text_items(
        self,
        text: str,
        html: str,
        page_url: str,
        items: list[AdvertisingTextItem],
        seen: set[tuple[str, str, str]],
    ) -> None:
        searchable = f"{text}\n{html}"
        self._add_regex_item("erid", self.erid_patterns, searchable, page_url, items, seen)
        self._add_regex_item("ad_label", (self.ad_label_pattern,), text, page_url, items, seen)
        self._add_regex_item(
            "advertiser_info",
            (self.advertiser_pattern,),
            text,
            page_url,
            items,
            seen,
        )
        self._add_regex_item(
            "sponsored_text",
            (self.sponsored_pattern,),
            text,
            page_url,
            items,
            seen,
        )

    def _collect_possible_ad_blocks(
        self,
        html: str,
        page_url: str,
        items: list[AdvertisingTextItem],
        seen: set[tuple[str, str, str]],
    ) -> None:
        if not html:
            return

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(True):
            if not isinstance(tag, Tag):
                continue

            tokens = self._attribute_tokens(tag)
            matched = sorted(tokens & self.possible_ad_tokens)
            if not matched:
                continue

            self._add_text_item(
                item_type="possible_ad_block",
                value=matched[0],
                page_url=page_url,
                evidence=self._tag_evidence(tag, matched[0]),
                items=items,
                seen=seen,
            )

    def _collect_external_services(
        self,
        external_services: ExternalServicesResult | None,
        services: list[AdvertisingServiceItem],
        seen: set[tuple[str, str, str | None]],
    ) -> None:
        if not external_services:
            return

        for item in external_services.items:
            url = item.url or item.provider or ""
            self._add_service(
                url=url,
                page_url=item.page_url,
                source="external_services",
                services=services,
                seen=seen,
                external_item=item,
            )

    def _collect_browser_services(
        self,
        browser_check: BrowserCheckResult | None,
        services: list[AdvertisingServiceItem],
        seen: set[tuple[str, str, str | None]],
    ) -> None:
        if not browser_check or not browser_check.items:
            return

        for page in browser_check.items:
            page_url = page.final_url or page.url
            for request in page.network_requests:
                self._add_service(
                    url=request.url,
                    page_url=page_url,
                    source="browser_network",
                    services=services,
                    seen=seen,
                )

    def _add_service(
        self,
        url: str,
        page_url: str | None,
        source: str,
        services: list[AdvertisingServiceItem],
        seen: set[tuple[str, str, str | None]],
        external_item: ExternalServiceItem | None = None,
    ) -> None:
        classification = self._classify_service(url, external_item)
        if not classification:
            return

        service_type, provider = classification
        domain = self._extract_domain(url)
        key = (url, source, page_url)
        if key in seen:
            return

        seen.add(key)
        services.append(
            AdvertisingServiceItem(
                service_type=service_type,
                provider=provider,
                url=url,
                domain=domain,
                page_url=page_url,
                source=source,
            )
        )

    def _classify_service(
        self,
        url: str,
        external_item: ExternalServiceItem | None = None,
    ) -> tuple[str, str] | None:
        value = (url or "").lower()
        if external_item and external_item.service_type == "advertising":
            provider = external_item.provider or "Advertising service"
            return self._service_type_for_value(value, provider), provider

        for marker, service_type, provider in self.service_signatures:
            if marker in value:
                return service_type, provider

        domain = self._extract_domain(url) or ""
        domain_tokens = re.split(r"[-.]", domain)
        if "ads" in domain_tokens or domain.startswith("ad."):
            return "unknown", "Unknown advertising service"
        return None

    def _service_type_for_value(self, value: str, provider: str) -> str:
        explicit = self._classify_service(value)
        if explicit:
            return explicit[0]
        if "social" in provider.lower():
            return "social_ads"
        return "advertising"

    def _add_regex_item(
        self,
        item_type: str,
        patterns: tuple[re.Pattern[str], ...],
        text: str,
        page_url: str,
        items: list[AdvertisingTextItem],
        seen: set[tuple[str, str, str]],
    ) -> None:
        for pattern in patterns:
            match = pattern.search(text or "")
            if not match:
                continue

            value = match.group(0)
            self._add_text_item(
                item_type=item_type,
                value=value,
                page_url=page_url,
                evidence=self._text_evidence(text, match.start(), match.end()),
                items=items,
                seen=seen,
            )
            return

    def _add_text_item(
        self,
        item_type: str,
        value: str,
        page_url: str,
        evidence: str,
        items: list[AdvertisingTextItem],
        seen: set[tuple[str, str, str]],
    ) -> None:
        key = (item_type, value, page_url)
        if key in seen:
            return

        seen.add(key)
        items.append(
            AdvertisingTextItem(
                item_type=item_type,
                value=value,
                page_url=page_url,
                evidence=evidence,
            )
        )

    def _page_text(self, page: PageData) -> str:
        if page.text:
            return page.text
        if not page.html:
            return ""
        return BeautifulSoup(page.html, "html.parser").get_text(" ", strip=True)

    def _attribute_tokens(self, tag: Tag) -> set[str]:
        values: list[str] = []
        for attr_name in ("class", "id", "data-ad-slot", "data-ad-client", "data-ad-format"):
            value = tag.get(attr_name)
            if isinstance(value, list):
                values.extend(str(item) for item in value)
            elif isinstance(value, str):
                values.append(value)

        tokens: set[str] = set()
        for value in values:
            for token in re.split(r"[\s_]+", value.lower()):
                cleaned = token.strip()
                if cleaned:
                    tokens.add(cleaned)
        return tokens

    def _tag_evidence(self, tag: Tag, token: str) -> str:
        identifier = tag.get("id")
        classes = tag.get("class")
        if identifier:
            return f"{tag.name}#{identifier}: {token}"
        if isinstance(classes, list) and classes:
            return f"{tag.name}.{'.'.join(classes[:3])}: {token}"
        return f"{tag.name}: {token}"

    def _text_evidence(self, text: str, start: int, end: int) -> str:
        left = max(start - 40, 0)
        right = min(end + 40, len(text))
        return re.sub(r"\s+", " ", text[left:right]).strip()

    def _normalize_url(self, url: str) -> str:
        return unescape(url).strip()

    def _extract_domain(self, url: str) -> str | None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            return None
        return parsed.hostname.lower().rstrip(".") if parsed.hostname else None

    def _warnings(
        self,
        found: bool,
        ad_services_found: bool,
        erid_found: bool,
        ad_marking_found: bool,
        possible_ad_blocks_found: bool,
    ) -> list[str]:
        warnings: list[str] = []
        if ad_services_found and not erid_found:
            warnings.append(
                "Обнаружены признаки подключения рекламных сервисов, но на проверенных страницах не найден erid; требуется ручная проверка."
            )
        if ad_services_found and not ad_marking_found:
            warnings.append(
                "Обнаружены признаки рекламных сервисов, но автоматическая проверка не нашла явной маркировки рекламы на проверенных страницах."
            )
        if possible_ad_blocks_found:
            warnings.append(
                "Обнаружены возможные рекламные блоки по HTML-признакам; требуется ручная проверка их назначения."
            )
        if not found:
            warnings.append("На проверенных страницах явные рекламные признаки не найдены.")
        return warnings
