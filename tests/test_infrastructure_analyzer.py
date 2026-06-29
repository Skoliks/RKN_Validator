import pytest

from app.analyzers.infrastructure_analyzer import InfrastructureAnalyzer
from app.schemas.browser import BrowserCheckResult, BrowserNetworkRequest, BrowserPageResult
from app.schemas.cookies import CookieAnalysisResult, CookieBeforeConsentItem
from app.schemas.infrastructure import (
    InfrastructureAnalysisResult,
    InfrastructureDomainItem,
    InfrastructureServiceItem,
)
from app.schemas.pages import CrawlResult, PageData
from app.schemas.site import SiteInfo
from app.services.check_service import CheckService
from app.services.report_service import ReportService
from app.services.risk_service import RiskService
from tests.test_check_service import FakeAvailabilityService, FakeBrowserCheckService, FakeCrawlService, make_available
from tests.test_report_service import make_check_result
from tests.test_risk_service import factor_codes, make_check


def summary_text(report) -> str:
    return " ".join(report.summary)


def site(domain: str = "example.ru", url: str = "https://example.ru") -> SiteInfo:
    return SiteInfo(
        original_input=url,
        normalized_url=url,
        final_url=url,
        domain=domain,
        domain_zone=domain.rsplit(".", 1)[-1] if "." in domain else None,
    )


def page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def analyze_html(html: str, domain: str = "example.ru") -> InfrastructureAnalysisResult:
    return InfrastructureAnalyzer().analyze(site=site(domain), pages=[page(html)])


def domain_item(result: InfrastructureAnalysisResult, domain: str) -> InfrastructureDomainItem:
    return next(item for item in result.domains if item.domain == domain)


def service_item(result: InfrastructureAnalysisResult, domain: str) -> InfrastructureServiceItem:
    return next(item for item in result.services if item.domain == domain)


def test_infrastructure_analyzer_adds_site_domain() -> None:
    result = InfrastructureAnalyzer().analyze(site=site("infocom.io", "https://infocom.io"), pages=[])

    item = domain_item(result, "infocom.io")
    assert item.category == "site"
    assert item.is_third_party is False
    assert item.source == "site_domain"


def test_infrastructure_analyzer_classifies_unpkg_as_cdn_foreign() -> None:
    result = analyze_html('<script src="https://unpkg.com/lib.js"></script>')

    item = domain_item(result, "unpkg.com")
    assert item.category == "cdn"
    assert item.likely_foreign is True
    assert result.cdn_services_found is True


def test_infrastructure_analyzer_classifies_fonts_gstatic_as_fonts_foreign() -> None:
    result = analyze_html('<link href="https://fonts.gstatic.com/font.woff2">')

    item = domain_item(result, "fonts.gstatic.com")
    assert item.category == "fonts"
    assert item.likely_foreign is True
    assert result.fonts_services_found is True


def test_infrastructure_analyzer_classifies_yandex_metrika_as_analytics_russian() -> None:
    result = analyze_html('<img src="https://mc.yandex.ru/watch/1">')

    item = domain_item(result, "mc.yandex.ru")
    assert item.category == "analytics"
    assert item.likely_russian is True
    assert result.analytics_services_found is True


def test_infrastructure_analyzer_classifies_googleads_as_advertising_foreign() -> None:
    result = analyze_html('<script src="https://googleads.g.doubleclick.net/pagead/id"></script>')

    item = domain_item(result, "googleads.g.doubleclick.net")
    assert item.category == "advertising"
    assert item.likely_foreign is True
    assert result.advertising_services_found is True


def test_infrastructure_analyzer_classifies_youtube_as_video_foreign() -> None:
    result = analyze_html('<iframe src="https://www.youtube.com/embed/1"></iframe>')

    item = domain_item(result, "www.youtube.com")
    assert item.category == "video"
    assert item.likely_foreign is True
    assert result.video_services_found is True


def test_infrastructure_analyzer_classifies_whatsapp_as_messenger_foreign() -> None:
    result = analyze_html('<a href="https://whatsapp.com/send?phone=1"></a>')

    item = domain_item(result, "whatsapp.com")
    assert item.category == "messenger"
    assert item.likely_foreign is True
    assert result.messenger_services_found is True


def test_infrastructure_analyzer_classifies_bitrix24_ru_as_crm_russian() -> None:
    result = analyze_html('<script src="https://bitrix24.ru/widget.js"></script>')

    item = domain_item(result, "bitrix24.ru")
    assert item.category == "crm"
    assert item.likely_russian is True
    assert result.crm_services_found is True


def test_infrastructure_analyzer_does_not_mark_io_site_domain_as_foreign() -> None:
    result = InfrastructureAnalyzer().analyze(site=site("infocom.io", "https://infocom.io"), pages=[])

    item = domain_item(result, "infocom.io")
    assert item.likely_foreign is None
    assert item.likely_russian is None


def test_infrastructure_analyzer_deduplicates_domains_across_sources() -> None:
    browser_check = BrowserCheckResult(
        enabled=True,
        performed=True,
        pages_checked=1,
        items=[
            BrowserPageResult(
                browser_check_performed=True,
                url="https://example.ru",
                network_requests=[
                    BrowserNetworkRequest(
                        url="https://mc.yandex.ru/watch/1",
                        domain="mc.yandex.ru",
                        resource_type="script",
                        is_third_party=True,
                    )
                ],
            )
        ],
    )
    cookies = CookieAnalysisResult(
        browser_check_available=True,
        analyzed=True,
        cookies_before_consent=[
            CookieBeforeConsentItem(
                name="_ym_uid",
                domain="mc.yandex.ru",
                is_third_party=True,
                category="analytics",
            )
        ],
    )

    result = InfrastructureAnalyzer().analyze(
        site=site(),
        browser_check=browser_check,
        cookies=cookies,
    )

    assert [item.domain for item in result.domains].count("mc.yandex.ru") == 1


def test_infrastructure_analyzer_warns_about_foreign_services() -> None:
    result = analyze_html('<script src="https://unpkg.com/lib.js"></script>')

    assert result.foreign_services_found is True
    assert any("иностранных сервисов" in warning for warning in result.warnings)


def test_risk_service_adds_foreign_infrastructure_factor() -> None:
    result = RiskService().assess(
        infrastructure=InfrastructureAnalysisResult(
            checked=True,
            external_domains_found=True,
            foreign_services_found=True,
            domains=[
                InfrastructureDomainItem(
                    domain="unpkg.com",
                    category="cdn",
                    is_third_party=True,
                    likely_foreign=True,
                    source="html",
                )
            ],
            services=[
                InfrastructureServiceItem(
                    provider="UNPKG",
                    category="cdn",
                    domain="unpkg.com",
                    likely_foreign=True,
                    source="html",
                )
            ],
        ),
        check=make_check(),
    )

    assert "foreign_infrastructure_services_detected" in factor_codes(result)


def test_risk_service_adds_analytics_infrastructure_factor() -> None:
    result = RiskService().assess(
        infrastructure=InfrastructureAnalysisResult(
            checked=True,
            external_domains_found=True,
            analytics_services_found=True,
            domains=[
                InfrastructureDomainItem(
                    domain="mc.yandex.ru",
                    category="analytics",
                    is_third_party=True,
                    likely_russian=True,
                    source="html",
                )
            ],
            services=[
                InfrastructureServiceItem(
                    provider="Yandex",
                    category="analytics",
                    domain="mc.yandex.ru",
                    likely_russian=True,
                    source="html",
                )
            ],
        ),
        check=make_check(),
    )

    assert "analytics_infrastructure_detected" in factor_codes(result)


def test_risk_service_does_not_add_foreign_factor_when_not_foreign() -> None:
    result = RiskService().assess(
        infrastructure=InfrastructureAnalysisResult(
            checked=True,
            external_domains_found=True,
            foreign_services_found=False,
            domains=[
                InfrastructureDomainItem(
                    domain="mc.yandex.ru",
                    category="analytics",
                    is_third_party=True,
                    likely_russian=True,
                    source="html",
                )
            ],
        ),
        check=make_check(),
    )

    assert "foreign_infrastructure_services_detected" not in factor_codes(result)
    assert "external_infrastructure_services_detected" in factor_codes(result)


def test_report_service_mentions_infrastructure_cautiously() -> None:
    report = ReportService().build(
        make_check_result(
            risk_level="medium",
            risk_score=35,
            infrastructure=InfrastructureAnalysisResult(
                checked=True,
                external_domains_found=True,
                foreign_services_found=True,
                analytics_services_found=True,
                domains=[
                    InfrastructureDomainItem(
                        domain="google-analytics.com",
                        category="analytics",
                        is_third_party=True,
                        likely_foreign=True,
                        source="html",
                    )
                ],
            ),
        )
    )

    assert "Обнаружены сторонние домены и внешние инфраструктурные сервисы." in summary_text(report)
    assert "Обнаружены признаки использования иностранных сервисов" in summary_text(report)
    assert "Внешняя инфраструктура и сторонние домены" in report.checked_areas
    assert "Проверить условия обработки и передачи данных при использовании сторонних сервисов." in report.recommendations
    assert "сайт размещён за рубежом" not in summary_text(report).lower()
    assert "данные хранятся за границей" not in summary_text(report).lower()


@pytest.mark.asyncio
async def test_check_service_includes_infrastructure_result() -> None:
    service = CheckService(
        availability_service=FakeAvailabilityService(make_available()),
        crawl_service=FakeCrawlService(
            CrawlResult(
                pages=[
                    page(
                        '<html lang="ru"><script src="https://unpkg.com/lib.js"></script></html>'
                    )
                ]
            )
        ),
        browser_check_service=FakeBrowserCheckService(enabled=False),
    )

    result = await service.check("https://example.ru")

    assert result.infrastructure is not None
    assert result.infrastructure.checked is True
    assert result.infrastructure.external_domains_found is True
    assert service_item(result.infrastructure, "unpkg.com").category == "cdn"
