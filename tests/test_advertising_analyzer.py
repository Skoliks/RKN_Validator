import pytest

from app.analyzers.advertising_analyzer import AdvertisingAnalyzer
from app.schemas.advertising import AdvertisingAnalysisResult, AdvertisingServiceItem
from app.schemas.browser import BrowserCheckResult, BrowserNetworkRequest, BrowserPageResult
from app.schemas.pages import CrawlResult, PageData
from app.services.check_service import CheckService
from app.services.risk_service import RiskService
from app.services.report_service import ReportService
from tests.test_check_service import FakeAvailabilityService, FakeBrowserCheckService, FakeCrawlService, make_available
from tests.test_report_service import make_check_result
from tests.test_risk_service import factor_codes, make_check


def summary_text(report) -> str:
    return " ".join(report.summary)


def page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def browser_check_with_request(url: str, domain: str | None = None) -> BrowserCheckResult:
    return BrowserCheckResult(
        enabled=True,
        performed=True,
        pages_checked=1,
        items=[
            BrowserPageResult(
                browser_check_performed=True,
                url="https://example.ru",
                final_url="https://example.ru",
                network_requests=[
                    BrowserNetworkRequest(
                        url=url,
                        domain=domain,
                        is_third_party=True,
                    )
                ],
            )
        ],
    )


def test_advertising_analyzer_detects_erid() -> None:
    result = AdvertisingAnalyzer().analyze([page("<html>erid: abc123456</html>")])

    assert result.erid_found is True
    assert any(item.item_type == "erid" for item in result.text_items)


def test_advertising_analyzer_does_not_treat_timer_id_as_erid() -> None:
    result = AdvertisingAnalyzer().analyze(
        [page("<script>let timerID = setInterval(function () {}, 1000)</script>")]
    )

    assert result.erid_found is False
    assert not any("setInterval" in item.value for item in result.text_items)


def test_advertising_analyzer_detects_ad_label() -> None:
    result = AdvertisingAnalyzer().analyze([page("<p>Реклама</p>")])

    assert result.ad_marking_found is True
    assert any(item.item_type == "ad_label" for item in result.text_items)


def test_advertising_analyzer_detects_advertiser_info() -> None:
    result = AdvertisingAnalyzer().analyze([page("<p>Рекламодатель: ООО Ромашка</p>")])

    assert result.advertiser_info_found is True
    assert any(item.item_type == "advertiser_info" for item in result.text_items)


def test_advertising_analyzer_does_not_treat_marketing_as_ad_label() -> None:
    result = AdvertisingAnalyzer().analyze([page("<p>Маркетинг для бизнеса</p>")])

    assert result.ad_marking_found is False


def test_advertising_analyzer_detects_googleads_browser_network() -> None:
    result = AdvertisingAnalyzer().analyze(
        browser_check=browser_check_with_request(
            "https://googleads.g.doubleclick.net/pagead/id",
            domain="googleads.g.doubleclick.net",
        )
    )

    assert result.ad_services_found is True
    assert result.services[0].provider == "Google DoubleClick"
    assert result.services[0].service_type == "advertising"
    assert result.services[0].source == "browser_network"


def test_advertising_analyzer_detects_static_doubleclick_browser_network() -> None:
    result = AdvertisingAnalyzer().analyze(
        browser_check=browser_check_with_request(
            "https://static.doubleclick.net/instream/ad_status.js",
            domain="static.doubleclick.net",
        )
    )

    assert result.ad_services_found is True
    assert result.services[0].provider == "Google DoubleClick"


def test_advertising_analyzer_does_not_treat_yandex_metrika_as_ad_service() -> None:
    result = AdvertisingAnalyzer().analyze(
        browser_check=browser_check_with_request(
            "https://mc.yandex.ru/metrika/tag.js",
            domain="mc.yandex.ru",
        )
    )

    assert result.ad_services_found is False
    assert result.services == []


def test_advertising_analyzer_detects_adsbygoogle_class() -> None:
    result = AdvertisingAnalyzer().analyze([page('<ins class="adsbygoogle"></ins>')])

    assert result.possible_ad_blocks_found is True
    assert any(item.item_type == "possible_ad_block" for item in result.text_items)


def test_advertising_analyzer_does_not_detect_header_as_ad_block() -> None:
    result = AdvertisingAnalyzer().analyze([page('<header class="header"></header>')])

    assert result.possible_ad_blocks_found is False


def test_advertising_analyzer_warns_when_service_without_erid() -> None:
    result = AdvertisingAnalyzer().analyze(
        browser_check=browser_check_with_request("https://googleads.g.doubleclick.net/pagead/id")
    )

    assert any("не найден erid" in warning for warning in result.warnings)


def test_advertising_analyzer_warns_when_service_without_label() -> None:
    result = AdvertisingAnalyzer().analyze(
        browser_check=browser_check_with_request("https://googleads.g.doubleclick.net/pagead/id")
    )

    assert any("не нашла явной маркировки" in warning for warning in result.warnings)


def test_risk_service_adds_advertising_service_without_erid() -> None:
    result = RiskService().assess(
        advertising=AdvertisingAnalysisResult(
            found=True,
            ad_services_found=True,
            ad_marking_found=True,
            erid_found=False,
            services=[
                AdvertisingServiceItem(
                    service_type="advertising",
                    provider="Google DoubleClick",
                    url="https://googleads.g.doubleclick.net/pagead/id",
                    domain="googleads.g.doubleclick.net",
                    source="browser_network",
                )
            ],
        ),
        check=make_check(),
    )

    assert "advertising_service_without_erid" in factor_codes(result)


def test_risk_service_adds_advertising_service_without_label() -> None:
    result = RiskService().assess(
        advertising=AdvertisingAnalysisResult(
            found=True,
            ad_services_found=True,
            ad_marking_found=False,
            erid_found=True,
            services=[
                AdvertisingServiceItem(
                    service_type="advertising",
                    provider="Google DoubleClick",
                    url="https://googleads.g.doubleclick.net/pagead/id",
                    domain="googleads.g.doubleclick.net",
                    source="browser_network",
                )
            ],
        ),
        check=make_check(),
    )

    assert "advertising_service_without_label" in factor_codes(result)


def test_risk_service_skips_advertising_factors_when_not_found() -> None:
    result = RiskService().assess(
        advertising=AdvertisingAnalysisResult(found=False),
        check=make_check(),
    )

    assert {
        "advertising_service_without_erid",
        "advertising_service_without_label",
        "possible_ad_blocks_detected",
    }.isdisjoint(factor_codes(result))


def test_report_service_mentions_advertising_services_cautiously() -> None:
    report = ReportService().build(
        make_check_result(
            risk_level="medium",
            risk_score=35,
            advertising=AdvertisingAnalysisResult(
                found=True,
                ad_services_found=True,
                erid_found=False,
                ad_marking_found=False,
                services=[
                    AdvertisingServiceItem(
                        service_type="advertising",
                        provider="Google DoubleClick",
                        url="https://googleads.g.doubleclick.net/pagead/id",
                        domain="googleads.g.doubleclick.net",
                        source="browser_network",
                    )
                ],
            ),
        )
    )

    assert "Обнаружены признаки подключения рекламных сервисов." in summary_text(report)
    assert "На проверенных страницах не найден erid" in summary_text(report)
    assert "Явная маркировка рекламы не была найдена автоматически." in summary_text(report)
    assert "нарушает закон" not in summary_text(report).lower()


@pytest.mark.asyncio
async def test_check_service_includes_advertising_result() -> None:
    service = CheckService(
        availability_service=FakeAvailabilityService(make_available()),
        crawl_service=FakeCrawlService(
            CrawlResult(
                pages=[
                    page(
                        '<script src="https://googleads.g.doubleclick.net/pagead/id"></script>'
                    )
                ]
            )
        ),
        browser_check_service=FakeBrowserCheckService(enabled=False),
    )

    result = await service.check("https://example.ru")

    assert result.advertising is not None
    assert result.advertising.ad_services_found is True
    assert result.advertising.services[0].provider == "Google DoubleClick"
