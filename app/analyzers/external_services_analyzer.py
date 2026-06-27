import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.pages import PageData


class ExternalServicesAnalyzer:
    known_services = {
        "googletagmanager.com": ("analytics", "Google Tag Manager"),
        "google-analytics.com": ("analytics", "Google Analytics"),
        "mc.yandex.ru": ("analytics", "Yandex Metrika"),
        "metrika.yandex.ru": ("analytics", "Yandex Metrika"),
        "connect.facebook.net": ("social", "Facebook"),
        "facebook.com": ("social", "Facebook"),
        "doubleclick.net": ("advertising", "DoubleClick"),
        "vk.com": ("social", "VK"),
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
                    domain = self._extract_domain(url)
                    if not domain or domain == page_domain:
                        continue

                    service_type, provider = self._classify_service(domain)
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
                        )
                    )

            for url in self._extract_fallback_urls(page.html, page_url):
                domain = self._extract_domain(url)
                if not domain or domain == page_domain:
                    continue

                service_type, provider = self._classify_service(domain)
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
                    )
                )

        return ExternalServicesResult(found=bool(items), items=items)

    def _build_url(self, tag: Tag, attr_name: str, base_url: str) -> str:
        value = tag.get(attr_name)
        raw_url = value.strip() if isinstance(value, str) else ""
        return urljoin(base_url, raw_url)

    def _extract_fallback_urls(self, html: str, base_url: str) -> list[str]:
        return [
            urljoin(base_url, match.group(1).strip())
            for match in self.fallback_url_pattern.finditer(html)
        ]

    def _extract_domain(self, url: str) -> str | None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            return None
        return parsed.hostname.lower().rstrip(".") if parsed.hostname else None

    def _classify_service(self, domain: str) -> tuple[str, str | None]:
        for known_domain, service_info in self.known_services.items():
            if domain == known_domain or domain.endswith(f".{known_domain}"):
                return service_info

        return "external_link", None
