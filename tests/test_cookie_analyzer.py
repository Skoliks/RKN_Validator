import pytest

from app.analyzers.cookie_analyzer import CookieAnalyzer
from app.schemas.browser import (
    BrowserCheckResult,
    BrowserCookieItem,
    CookieInteractionResult,
    BrowserNetworkRequest,
    BrowserPageResult,
)
from app.schemas.cookies import CookieAnalysisResult
from app.schemas.pages import CrawlResult, PageData
from app.schemas.availability import AvailabilityInfo
from app.schemas.site import SiteInfo
from app.services.check_service import CheckService


class FakeAvailabilityService:
    async def check(self, site: SiteInfo) -> AvailabilityInfo:
        return AvailabilityInfo(available=True, status_code=200, message="Сайт доступен.")


class FakeCrawlService:
    async def crawl(self, site: SiteInfo) -> CrawlResult:
        return CrawlResult(pages=[PageData(url=site.normalized_url, final_url=site.normalized_url, status_code=200, html="<html></html>")])


class FakeBrowserCheckService:
    enabled = True

    async def check(self, pages_or_urls, source_domain: str | None = None) -> BrowserCheckResult:
        return browser_check(
            cookies=[BrowserCookieItem(name="_ym_uid", domain="example.ru")],
            requests=[
                BrowserNetworkRequest(
                    url="https://mc.yandex.ru/watch/1",
                    domain="mc.yandex.ru",
                    resource_type="script",
                    is_third_party=True,
                )
            ],
        )


def browser_check(
    cookies: list[BrowserCookieItem] | None = None,
    requests: list[BrowserNetworkRequest] | None = None,
    visible_text: str | None = None,
    interaction: CookieInteractionResult | None = None,
) -> BrowserCheckResult:
    return BrowserCheckResult(
        enabled=True,
        performed=True,
        pages_checked=1,
        items=[
            BrowserPageResult(
                browser_check_performed=True,
                url="https://example.ru",
                final_url="https://example.ru",
                visible_text=visible_text,
                cookies_after_load=cookies or [],
                network_requests=requests or [],
            )
        ],
        cookie_interaction=interaction,
    )


def test_cookie_analyzer_without_browser_check_returns_not_analyzed() -> None:
    result = CookieAnalyzer().analyze(None)

    assert result.analyzed is False
    assert result.browser_check_available is False
    assert "Браузерная проверка не выполнялась" in result.warnings[0]


def test_cookie_analyzer_detects_yandex_cookie_as_analytics() -> None:
    result = CookieAnalyzer().analyze(
        browser_check(cookies=[BrowserCookieItem(name="_ym_uid", domain="example.ru")])
    )

    assert result.cookies_before_consent_found is True
    assert result.cookies_before_consent[0].category == "analytics"


def test_cookie_analyzer_detects_youtube_cookie_as_third_party_video() -> None:
    result = CookieAnalyzer().analyze(
        browser_check(cookies=[BrowserCookieItem(name="VISITOR_INFO1_LIVE", domain=".youtube.com")])
    )

    assert result.third_party_cookies_before_consent_found is True
    assert result.cookies_before_consent[0].category == "video"


def test_cookie_analyzer_detects_yandex_metrika_request() -> None:
    result = CookieAnalyzer().analyze(
        browser_check(
            requests=[
                BrowserNetworkRequest(
                    url="https://mc.yandex.ru/watch/1",
                    domain="mc.yandex.ru",
                    resource_type="script",
                    is_third_party=True,
                )
            ]
        )
    )

    assert result.analytics_requests_before_consent_found is True
    assert result.requests_before_consent[0].category == "analytics"


def test_cookie_analyzer_detects_doubleclick_request() -> None:
    result = CookieAnalyzer().analyze(
        browser_check(
            requests=[
                BrowserNetworkRequest(
                    url="https://doubleclick.net/activity",
                    domain="doubleclick.net",
                    resource_type="script",
                    is_third_party=True,
                )
            ]
        )
    )

    assert result.advertising_requests_before_consent_found is True
    assert result.requests_before_consent[0].category == "advertising"


def test_cookie_analyzer_detects_youtube_request_as_video() -> None:
    result = CookieAnalyzer().analyze(
        browser_check(
            requests=[
                BrowserNetworkRequest(
                    url="https://youtube.com/embed/1",
                    domain="youtube.com",
                    resource_type="iframe",
                    is_third_party=True,
                )
            ]
        )
    )

    assert result.third_party_requests_before_consent_found is True
    assert result.requests_before_consent[0].category == "video"


def test_cookie_analyzer_deduplicates_requests_before_consent() -> None:
    result = CookieAnalyzer().analyze(
        browser_check(
            requests=[
                BrowserNetworkRequest(
                    url="https://doubleclick.net/activity",
                    path="/activity",
                    domain="doubleclick.net",
                    resource_type="script",
                    is_third_party=True,
                ),
                BrowserNetworkRequest(
                    url="https://doubleclick.net/activity",
                    path="/activity",
                    domain="doubleclick.net",
                    resource_type="script",
                    is_third_party=True,
                ),
            ]
        )
    )

    assert len(result.requests_before_consent) == 1
    assert result.requests_before_consent[0].path == "/activity"


def test_cookie_analyzer_detects_cookie_banner_and_accept_button() -> None:
    result = CookieAnalyzer().analyze(browser_check(visible_text="Мы используем cookie. Принять"))

    assert result.banner_found is True
    assert result.accept_button_found is True


def test_cookie_analyzer_detects_reject_button() -> None:
    result = CookieAnalyzer().analyze(browser_check(visible_text="Файлы cookie Отклонить"))

    assert result.reject_button_found is True


def test_cookie_analyzer_detects_settings_button() -> None:
    result = CookieAnalyzer().analyze(browser_check(visible_text="Файлы cookie Настроить"))

    assert result.settings_button_found is True


def test_cookie_analyzer_warns_when_banner_has_no_reject_button() -> None:
    result = CookieAnalyzer().analyze(browser_check(visible_text="Мы используем cookie. Принять"))

    assert "явная кнопка отклонения не была найдена автоматически" in " ".join(result.warnings)


def test_cookie_analyzer_does_not_warn_about_missing_banner_without_cookie_evidence() -> None:
    result = CookieAnalyzer().analyze(browser_check(visible_text="Example Domain"))

    assert result.analyzed is True
    assert result.cookies_before_consent_found is False
    assert not any("баннер не найден" in warning.lower() for warning in result.warnings)


def test_cookie_analyzer_does_not_warn_about_reject_button_without_cookie_evidence() -> None:
    result = CookieAnalyzer().analyze(
        browser_check(
            visible_text="Example Domain",
            interaction=CookieInteractionResult(
                enabled=True,
                performed=True,
                banner_found=False,
                reject_clicked=False,
                accept_clicked=False,
            ),
        )
    )

    assert result.warnings == []


def test_cookie_analyzer_preserves_text_banner_when_interaction_does_not_find_it() -> None:
    result = CookieAnalyzer().analyze(
        browser_check(
            visible_text="Мы используем cookie. Принять",
            interaction=CookieInteractionResult(
                enabled=True,
                performed=True,
                banner_found=False,
                reject_clicked=False,
                accept_clicked=False,
                warnings=["Cookie banner was not found automatically."],
            ),
        )
    )

    assert result.banner_found is True
    assert not any("banner was not found" in warning.lower() for warning in result.warnings)


def test_cookie_analyzer_deduplicates_reject_button_warnings() -> None:
    result = CookieAnalyzer().analyze(
        browser_check(
            visible_text="Мы используем cookie. Принять",
            interaction=CookieInteractionResult(
                enabled=True,
                performed=True,
                banner_found=True,
                reject_clicked=False,
                accept_clicked=False,
            ),
        )
    )

    assert " ".join(result.warnings).count("кнопка отклонения") == 1


@pytest.mark.asyncio
async def test_check_service_includes_cookie_analysis_when_browser_check_enabled() -> None:
    service = CheckService(
        availability_service=FakeAvailabilityService(),
        crawl_service=FakeCrawlService(),
        browser_check_service=FakeBrowserCheckService(),
    )

    result = await service.check("https://example.ru")

    assert result.cookies is not None
    assert result.cookies.analyzed is True
    assert result.cookies.cookies_before_consent_found is True
    assert result.cookies.analytics_requests_before_consent_found is True


def test_cookie_analysis_result_model_defaults() -> None:
    result = CookieAnalysisResult()

    assert result.analyzed is False
    assert result.banner_candidates == []
