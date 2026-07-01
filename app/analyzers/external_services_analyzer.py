import re
import logging
from html import unescape
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.pages import PageData


class ExternalServicesAnalyzer:
    logger = logging.getLogger(__name__)
    known_services = {
        "googletagmanager.com": ("analytics", "Google Tag Manager", True),
        "google-analytics.com": ("analytics", "Google Analytics", True),
        "mc.yandex.ru": ("analytics", "Yandex Metrika", False),
        "metrika.yandex.ru": ("analytics", "Yandex Metrika", False),
        "yastatic.net": ("cdn", "Yandex", False),
        "unpkg.com": ("cdn", "UNPKG", True),
        "connect.facebook.net": ("social_network", "Facebook", True),
        "facebook.com": ("social_network", "Facebook", True),
        "instagram.com": ("social_network", "Instagram", True),
        "wa.me": ("messenger", "WhatsApp", True),
        "doubleclick.net": ("advertising", "DoubleClick", True),
        "vk.com": ("social_network", "VK", False),
        "bitrix24.ru": ("crm_widget", "Bitrix24", False),
        "bitrix24.net": ("crm_widget", "Bitrix24", False),
        "bitrix24.com": ("crm_widget", "Bitrix24", True),
    }
    selectors = (
        ("script", "src"),
        ("link", "href"),
        ("iframe", "src"),
        ("img", "src"),
        ("form", "action"),
        ("a", "href"),
    )
    fallback_url_pattern = re.compile(
        r"\b(?:src|href|action)\s*=\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )

    def analyze(self, pages: list[PageData]) -> ExternalServicesResult:
        items: list[ExternalServiceItem] = []
        seen: set[tuple[str, str, str]] = set()

        for page in pages:
            if not page.html:
                continue

            page_url = page.final_url or page.url
            page_domain = self._extract_domain(page_url)
            soup = BeautifulSoup(page.html, "html.parser")

            for tag_name, attr_name in self.selectors:
                for tag in soup.find_all(tag_name):
                    if not isinstance(tag, Tag):
                        continue

                    url = self._build_url(tag, attr_name, page_url)
                    if not url:
                        continue
                    domain = self._extract_domain(url)
                    if not domain or domain == page_domain:
                        continue

                    service_type, provider, foreign = self._classify_service(domain, tag.name)
                    key = (domain, url, page_url)
                    if key in seen:
                        continue

                    seen.add(key)
                    items.append(
                        ExternalServiceItem(
                            service_type=service_type,
                            provider=provider,
                            url=url,
                            page_url=page_url,
                            foreign=foreign,
                        )
                    )

            for url in self._extract_fallback_urls(page.html, page_url):
                domain = self._extract_domain(url)
                if not domain or domain == page_domain:
                    continue

                service_type, provider, foreign = self._classify_service(domain, None)
                key = (domain, url, page_url)
                if key in seen:
                    continue

                seen.add(key)
                items.append(
                    ExternalServiceItem(
                        service_type=service_type,
                        provider=provider,
                        url=url,
                        page_url=page_url,
                        foreign=foreign,
                    )
                )

        return ExternalServicesResult(found=bool(items), items=items)

    def _build_url(self, tag: Tag, attr_name: str, base_url: str) -> str | None:
        value = tag.get(attr_name)
        raw_url = value.strip() if isinstance(value, str) else ""
        if self._should_skip_raw_url(raw_url):
            return None
        try:
            return self._normalize_url(urljoin(base_url, raw_url))
        except ValueError:
            self.logger.debug("Skipping invalid external service URL: %r", raw_url)
            return None

    def _extract_fallback_urls(self, html: str, base_url: str) -> list[str]:
        urls: list[str] = []
        for match in self.fallback_url_pattern.finditer(html):
            raw_url = match.group(1).strip()
            if self._should_skip_raw_url(raw_url):
                continue
            try:
                normalized = self._normalize_url(urljoin(base_url, raw_url))
            except ValueError:
                self.logger.debug("Skipping invalid fallback external service URL: %r", raw_url)
                continue
            if normalized:
                urls.append(normalized)
        return urls

    def _normalize_url(self, url: str) -> str | None:
        normalized = unescape(url).strip()
        if self._should_skip_raw_url(normalized):
            return None
        try:
            urlsplit(normalized)
        except ValueError:
            self.logger.debug("Skipping invalid normalized external service URL: %r", url)
            return None
        return normalized

    def _extract_domain(self, url: str) -> str | None:
        try:
            parsed = urlsplit(url)
        except ValueError:
            self.logger.debug("Skipping external service URL with invalid domain: %r", url)
            return None
        if parsed.scheme not in {"http", "https"}:
            return None
        return parsed.hostname.lower().rstrip(".") if parsed.hostname else None

    def _classify_service(self, domain: str, tag_name: str | None = None) -> tuple[str, str | None, bool]:
        for known_domain, service_info in self.known_services.items():
            if domain == known_domain or domain.endswith(f".{known_domain}"):
                return service_info

        return ("external_link" if tag_name == "a" else "external_resource"), None, True

    def _should_skip_raw_url(self, raw_url: str) -> bool:
        if not raw_url:
            return True
        lowered = raw_url.strip().lower()
        if lowered.startswith(("#", "javascript:", "mailto:", "tel:", "data:", "{{")):
            return True
        if "{{" in raw_url or "}}" in raw_url or "<%" in raw_url or "%>" in raw_url:
            return True
        if ("[" in raw_url or "]" in raw_url) and not self._has_balanced_brackets(raw_url):
            return True
        return False

    def _has_balanced_brackets(self, value: str) -> bool:
        return value.count("[") == value.count("]") and value.find("[") <= value.find("]")
