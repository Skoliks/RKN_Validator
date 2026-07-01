from html import unescape
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.advertising import AdvertisingAnalysisResult
from app.schemas.browser import BrowserCheckResult
from app.schemas.cookies import CookieAnalysisResult
from app.schemas.external_services import ExternalServicesResult
from app.schemas.infrastructure import (
    InfrastructureAnalysisResult,
    InfrastructureDomainItem,
    InfrastructureServiceItem,
)
from app.schemas.pages import PageData
from app.schemas.site import SiteInfo


class InfrastructureAnalyzer:
    evidence_limit = 300
    html_selectors = (
        ("script", "src"),
        ("link", "href"),
        ("img", "src"),
        ("iframe", "src"),
        ("form", "action"),
        ("a", "href"),
    )
    category_markers = {
        "cdn": ("unpkg.com", "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "cloudflare.com", "cloudfront.net"),
        "fonts": ("fonts.gstatic.com", "fonts.googleapis.com"),
        "analytics": ("mc.yandex.ru", "metrika.yandex.ru", "google-analytics.com", "googletagmanager.com"),
        "advertising": (
            "doubleclick.net",
            "googleads.g.doubleclick.net",
            "googlesyndication.com",
            "googleadservices.com",
            "an.yandex.ru",
            "yabs.yandex.ru",
            "yandexadexchange.net",
        ),
        "video": ("youtube.com", "www.youtube.com", "img.youtube.com", "ytimg.com", "i.ytimg.com", "googlevideo.com"),
        "social": ("facebook.com", "instagram.com", "vk.com", "ok.ru", "tiktok.com"),
        "messenger": ("whatsapp.com", "web.whatsapp.com", "telegram.org", "t.me"),
        "crm": ("bitrix24.ru", "bitrix24.com", "b24.ru", "amocrm.ru", "amocrm.com"),
        "maps": ("maps.google.com", "google.com/maps", "yandex.ru/maps", "api-maps.yandex.ru"),
        "payment": ("yookassa.ru", "payment.yandex.net", "robokassa.ru", "cloudpayments.ru", "tinkoff.ru", "sberbank.ru"),
    }
    likely_russian_markers = (
        "yandex.ru",
        "mc.yandex.ru",
        "metrika.yandex.ru",
        "bitrix24.ru",
        "b24.ru",
        "vk.com",
        "ok.ru",
        "yookassa.ru",
        "robokassa.ru",
        "cloudpayments.ru",
        "tinkoff.ru",
        "sberbank.ru",
    )
    likely_foreign_markers = (
        "google.com",
        "googleapis.com",
        "gstatic.com",
        "googlevideo.com",
        "youtube.com",
        "ytimg.com",
        "doubleclick.net",
        "googleads.g.doubleclick.net",
        "facebook.com",
        "instagram.com",
        "whatsapp.com",
        "tiktok.com",
        "unpkg.com",
        "cloudflare.com",
        "cloudfront.net",
        "jsdelivr.net",
    )

    def analyze(
        self,
        site: SiteInfo,
        pages: list[PageData] | None = None,
        external_services: ExternalServicesResult | None = None,
        browser_check: BrowserCheckResult | None = None,
        cookies: CookieAnalysisResult | None = None,
        advertising: AdvertisingAnalysisResult | None = None,
    ) -> InfrastructureAnalysisResult:
        domains: dict[str, InfrastructureDomainItem] = {}
        services: dict[tuple[str, str, str], InfrastructureServiceItem] = {}
        site_domain = self._normalize_domain(site.domain)

        if site_domain:
            self._add_domain(domains, site_domain, "site_domain", site.normalized_url, site_domain, "site")

        for page in pages or []:
            self._collect_html_domains(page, site_domain, domains, services)
        self._collect_external_services(external_services, site_domain, domains, services)
        self._collect_browser_domains(browser_check, site_domain, domains, services)
        self._collect_cookie_domains(cookies, site_domain, domains, services)
        self._collect_advertising_domains(advertising, site_domain, domains, services)

        domain_items = list(domains.values())
        service_items = list(services.values())
        external_domains_found = any(item.is_third_party for item in domain_items)
        foreign_services_found = any(
            item.likely_foreign is True and item.category != "site" for item in domain_items
        )
        russian_services_found = any(
            item.likely_russian is True and item.category != "site" for item in domain_items
        )
        categories = {item.category for item in domain_items if item.is_third_party}

        return InfrastructureAnalysisResult(
            checked=True,
            external_domains_found=external_domains_found,
            foreign_services_found=foreign_services_found,
            russian_services_found=russian_services_found,
            cdn_services_found="cdn" in categories,
            analytics_services_found="analytics" in categories,
            advertising_services_found="advertising" in categories,
            video_services_found="video" in categories,
            fonts_services_found="fonts" in categories,
            social_services_found="social" in categories,
            messenger_services_found="messenger" in categories,
            crm_services_found="crm" in categories,
            payment_services_found="payment" in categories,
            maps_services_found="maps" in categories,
            domains_count=len(domain_items),
            foreign_domains_count=sum(1 for item in domain_items if item.likely_foreign is True),
            russian_domains_count=sum(1 for item in domain_items if item.likely_russian is True),
            domains=domain_items,
            services=service_items,
            warnings=self._warnings(
                external_domains_found=external_domains_found,
                foreign_services_found=foreign_services_found,
                analytics_services_found="analytics" in categories,
                advertising_services_found="advertising" in categories,
                video_services_found="video" in categories,
            ),
        )

    def _collect_html_domains(
        self,
        page: PageData,
        site_domain: str | None,
        domains: dict[str, InfrastructureDomainItem],
        services: dict[tuple[str, str, str], InfrastructureServiceItem],
    ) -> None:
        if not page.html:
            return
        page_url = page.final_url or page.url
        soup = BeautifulSoup(page.html, "html.parser")
        for tag_name, attr_name in self.html_selectors:
            for tag in soup.find_all(tag_name):
                if not isinstance(tag, Tag):
                    continue
                raw = tag.get(attr_name)
                if not isinstance(raw, str) or not raw.strip():
                    continue
                url = self._build_url(raw.strip(), page_url)
                if not url:
                    continue
                domain = self._domain_from_url(url)
                if not domain:
                    continue
                category = self._classify_domain(domain, url)
                self._add_domain(domains, domain, "html", url, site_domain, category)
                self._add_service(services, domain, category, "html", url)

    def _collect_external_services(
        self,
        external_services: ExternalServicesResult | None,
        site_domain: str | None,
        domains: dict[str, InfrastructureDomainItem],
        services: dict[tuple[str, str, str], InfrastructureServiceItem],
    ) -> None:
        if not external_services:
            return
        for item in external_services.items:
            domain = self._domain_from_url(item.url or "") or self._normalize_domain(item.provider or "")
            if not domain:
                continue
            category = self._category_from_external_type(item.service_type, domain, item.url)
            evidence = item.url or item.provider
            self._add_domain(domains, domain, "external_services", evidence, site_domain, category)
            self._add_service(services, domain, category, "external_services", evidence, item.provider)

    def _collect_browser_domains(
        self,
        browser_check: BrowserCheckResult | None,
        site_domain: str | None,
        domains: dict[str, InfrastructureDomainItem],
        services: dict[tuple[str, str, str], InfrastructureServiceItem],
    ) -> None:
        if not browser_check:
            return
        for page in browser_check.items:
            for request in page.network_requests:
                domain = self._normalize_domain(request.domain or "") or self._domain_from_url(request.url)
                if not domain:
                    continue
                category = self._classify_domain(domain, request.url)
                if category == "unknown" and request.is_third_party and request.resource_type in {"xhr", "fetch"}:
                    category = "api"
                self._add_domain(domains, domain, "browser_network", request.url, site_domain, category)
                self._add_service(services, domain, category, "browser_network", request.url)

    def _collect_cookie_domains(
        self,
        cookies: CookieAnalysisResult | None,
        site_domain: str | None,
        domains: dict[str, InfrastructureDomainItem],
        services: dict[tuple[str, str, str], InfrastructureServiceItem],
    ) -> None:
        if not cookies:
            return
        for cookie in cookies.cookies_before_consent:
            domain = self._normalize_domain(cookie.domain or "")
            if not domain:
                continue
            category = self._classify_domain(domain, domain)
            self._add_domain(domains, domain, "cookies", cookie.name, site_domain, category)
            self._add_service(services, domain, category, "cookies", cookie.name)

    def _collect_advertising_domains(
        self,
        advertising: AdvertisingAnalysisResult | None,
        site_domain: str | None,
        domains: dict[str, InfrastructureDomainItem],
        services: dict[tuple[str, str, str], InfrastructureServiceItem],
    ) -> None:
        if not advertising:
            return
        for item in advertising.services:
            domain = self._normalize_domain(item.domain or "") or self._domain_from_url(item.url)
            if not domain:
                continue
            category = self._category_from_advertising_type(item.service_type, domain, item.url)
            self._add_domain(domains, domain, "advertising", item.url, site_domain, category)
            self._add_service(services, domain, category, "advertising", item.url, item.provider)

    def _add_domain(
        self,
        domains: dict[str, InfrastructureDomainItem],
        domain: str,
        source: str,
        evidence: str | None,
        site_domain: str | None,
        category: str | None = None,
    ) -> None:
        normalized = self._normalize_domain(domain)
        if not normalized:
            return
        existing = domains.get(normalized)
        if existing:
            if existing.category == "unknown" and category and category != "unknown":
                existing.category = category
            if not existing.evidence and evidence:
                existing.evidence = self._limit_evidence(evidence)
            return
        likely_foreign, likely_russian = self._likely_flags(normalized)
        item_category = category or self._classify_domain(normalized, evidence)
        domains[normalized] = InfrastructureDomainItem(
            domain=normalized,
            category=item_category,
            is_third_party=not self._same_or_subdomain(normalized, site_domain),
            likely_foreign=likely_foreign,
            likely_russian=likely_russian,
            source=source,
            evidence=self._limit_evidence(evidence) if evidence else None,
        )

    def _add_service(
        self,
        services: dict[tuple[str, str, str], InfrastructureServiceItem],
        domain: str,
        category: str,
        source: str,
        evidence: str | None,
        provider: str | None = None,
    ) -> None:
        if category in {"site", "unknown"}:
            return
        normalized = self._normalize_domain(domain)
        if not normalized:
            return
        service_provider = provider or self._provider_for_domain(normalized, category)
        key = (service_provider, normalized, category)
        if key in services:
            return
        likely_foreign, likely_russian = self._likely_flags(normalized)
        services[key] = InfrastructureServiceItem(
            provider=service_provider,
            category=category,
            domain=normalized,
            likely_foreign=likely_foreign,
            likely_russian=likely_russian,
            source=source,
            evidence=self._limit_evidence(evidence) if evidence else None,
        )

    def _classify_domain(self, domain: str, evidence: str | None = None) -> str:
        value = f"{domain} {evidence or ''}".lower()
        for category, markers in self.category_markers.items():
            if any(self._matches_marker(domain, marker) or marker in value for marker in markers):
                return category
        return "unknown"

    def _category_from_external_type(self, service_type: str, domain: str, evidence: str | None) -> str:
        mapping = {
            "cdn": "cdn",
            "analytics": "analytics",
            "tag_manager": "analytics",
            "advertising": "advertising",
            "social_network": "social",
            "messenger": "messenger",
            "crm_widget": "crm",
        }
        return mapping.get(service_type, self._classify_domain(domain, evidence))

    def _category_from_advertising_type(self, service_type: str, domain: str, evidence: str | None) -> str:
        if service_type in {"advertising", "retargeting", "analytics_with_ads"}:
            return "advertising"
        if service_type == "social_ads":
            return "social"
        return self._classify_domain(domain, evidence)

    def _likely_flags(self, domain: str) -> tuple[bool | None, bool | None]:
        if any(self._matches_marker(domain, marker) for marker in self.likely_foreign_markers):
            return True, None
        if any(self._matches_marker(domain, marker) for marker in self.likely_russian_markers):
            return None, True
        if domain.endswith(".ru") or domain.endswith(".рф"):
            return None, True
        return None, None

    def _provider_for_domain(self, domain: str, category: str) -> str:
        if self._matches_marker(domain, "doubleclick.net") or "google" in domain:
            return "Google"
        if "yandex" in domain:
            return "Yandex"
        if "youtube" in domain or "ytimg" in domain:
            return "YouTube"
        if "bitrix24" in domain or "b24.ru" in domain:
            return "Bitrix24"
        if "facebook" in domain:
            return "Facebook"
        if "whatsapp" in domain:
            return "WhatsApp"
        return category

    def _warnings(
        self,
        external_domains_found: bool,
        foreign_services_found: bool,
        analytics_services_found: bool,
        advertising_services_found: bool,
        video_services_found: bool,
    ) -> list[str]:
        warnings: list[str] = []
        if external_domains_found:
            warnings.append(
                "Обнаружены сторонние домены и внешние инфраструктурные сервисы; требуется ручная проверка их назначения."
            )
        if foreign_services_found:
            warnings.append(
                "Обнаружены признаки использования иностранных сервисов; автоматическая проверка не определяет фактическое место хранения данных."
            )
        if analytics_services_found:
            warnings.append(
                "Обнаружены аналитические сервисы; требуется ручная проверка условий обработки и передачи данных."
            )
        if advertising_services_found:
            warnings.append(
                "Обнаружены рекламные или связанные с рекламой сервисы; требуется ручная проверка их назначения."
            )
        if video_services_found:
            warnings.append(
                "Обнаружены внешние видеосервисы; они могут загружать сторонние ресурсы и cookies."
            )
        if not external_domains_found:
            warnings.append("Явные сторонние инфраструктурные домены на проверенных страницах не найдены.")
        return warnings

    def _domain_from_url(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            parsed = urlsplit(value)
        except ValueError:
            return None
        if parsed.scheme not in {"http", "https"}:
            return None
        return self._normalize_domain(parsed.hostname or "")

    def _normalize_url(self, value: str) -> str:
        return unescape(value).strip()

    def _build_url(self, raw_url: str, page_url: str) -> str | None:
        try:
            return self._normalize_url(urljoin(page_url, raw_url))
        except ValueError:
            return None

    def _normalize_domain(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().lower().lstrip(".").rstrip(".")
        if not normalized or "/" in normalized or " " in normalized:
            return None
        return normalized

    def _matches_marker(self, domain: str, marker: str) -> bool:
        marker = marker.lower()
        if "/" in marker:
            return marker in domain
        return domain == marker or domain.endswith(f".{marker}")

    def _same_or_subdomain(self, domain: str, site_domain: str | None) -> bool:
        if not site_domain:
            return False
        return domain == site_domain or domain.endswith(f".{site_domain}")

    def _limit_evidence(self, value: str | None) -> str | None:
        if not value:
            return None
        return " ".join(str(value).split())[: self.evidence_limit]
