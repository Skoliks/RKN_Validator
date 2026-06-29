import pytest

from app.infrastructure.browser_client import BrowserClient
from app.schemas.availability import AvailabilityInfo
from app.schemas.browser import (
    BrowserCheckResult,
    BrowserPageResult,
    BrowserCookieItem,
    CookieInteractionButton,
    CookieInteractionResult,
    CookieInteractionSnapshot,
)
from app.schemas.cookies import CookieAnalysisResult
from app.schemas.pages import CrawlResult, PageData
from app.schemas.site import SiteInfo
from app.services.check_service import CheckService
from app.services.report_service import ReportService
from app.services.risk_service import RiskService
from tests.test_report_service import make_check_result
from tests.test_risk_service import factor_codes, make_check


class FakeAvailabilityService:
    async def check(self, site: SiteInfo) -> AvailabilityInfo:
        return AvailabilityInfo(available=True, status_code=200, message="Сайт доступен.")


class FakeCrawlService:
    async def crawl(self, site: SiteInfo) -> CrawlResult:
        return CrawlResult(
            pages=[
                PageData(
                    url=site.normalized_url,
                    final_url=site.normalized_url,
                    status_code=200,
                    html="<html></html>",
                )
            ]
        )


class FakeBrowserCheckService:
    def __init__(self, enabled: bool, interaction: CookieInteractionResult | None = None) -> None:
        self.enabled = enabled
        self.cookie_interaction_enabled = bool(interaction)
        self.interaction = interaction

    async def check(self, pages_or_urls, source_domain: str | None = None) -> BrowserCheckResult:
        return BrowserCheckResult(
            enabled=True,
            performed=True,
            pages_checked=1,
            items=[
                BrowserPageResult(
                    browser_check_performed=True,
                    url="https://example.ru",
                    final_url="https://example.ru",
                    visible_text="Мы используем cookie. Принять",
                    cookies_after_load=[BrowserCookieItem(name="_ym_uid", domain="example.ru")],
                )
            ],
            cookie_interaction=self.interaction,
        )


def snapshot(stage: str, cookies_count: int = 0, analytics: int = 0, advertising: int = 0) -> CookieInteractionSnapshot:
    return CookieInteractionSnapshot(
        stage=stage,
        cookies=[],
        network_requests=[],
        cookies_count=cookies_count,
        third_party_cookies_count=0,
        analytics_requests_count=analytics,
        advertising_requests_count=advertising,
        third_party_requests_count=analytics + advertising,
    )


def interaction_result(
    buttons: list[CookieInteractionButton] | None = None,
    reject_clicked: bool = False,
    accept_clicked: bool = False,
    cookies_reduced: bool | None = None,
    analytics_reduced: bool | None = None,
    advertising_reduced: bool | None = None,
) -> CookieInteractionResult:
    return CookieInteractionResult(
        enabled=True,
        performed=True,
        banner_found=bool(buttons),
        buttons_found=buttons or [],
        reject_clicked=reject_clicked,
        accept_clicked=accept_clicked,
        initial_snapshot=snapshot("initial", cookies_count=3, analytics=2, advertising=1),
        after_reject_snapshot=snapshot("after_reject", cookies_count=1, analytics=2, advertising=1)
        if reject_clicked
        else None,
        after_accept_snapshot=snapshot("after_accept") if accept_clicked else None,
        cookies_reduced_after_reject=cookies_reduced,
        analytics_reduced_after_reject=analytics_reduced,
        advertising_reduced_after_reject=advertising_reduced,
    )


def button(label: str, action_type: str) -> CookieInteractionButton:
    return CookieInteractionButton(
        label=label,
        action_type=action_type,
        selector="[data-cookie-check-id='1']",
        visible=True,
        enabled=True,
    )


def test_cookie_interaction_disabled_when_browser_disabled() -> None:
    service = FakeBrowserCheckService(enabled=False)

    assert service.enabled is False
    assert service.cookie_interaction_enabled is False


def test_cookie_interaction_can_be_disabled_when_browser_enabled() -> None:
    service = FakeBrowserCheckService(enabled=True)

    assert service.enabled is True
    assert service.cookie_interaction_enabled is False


def test_browser_client_classifies_accept_button() -> None:
    assert BrowserClient()._classify_cookie_button("Принять") == "accept"


def test_browser_client_classifies_reject_button() -> None:
    assert BrowserClient()._classify_cookie_button("Отклонить") == "reject"


def test_browser_client_classifies_settings_button() -> None:
    assert BrowserClient()._classify_cookie_button("Настроить") == "settings"


def test_browser_client_does_not_classify_unsafe_business_button() -> None:
    assert BrowserClient()._classify_cookie_button("Заказать бесплатную консультацию") is None
    assert BrowserClient()._classify_cookie_button("Submit order") is None


def test_cookie_interaction_result_without_reject_button_has_warning_after_analysis() -> None:
    result = interaction_result(buttons=[button("Принять", "accept")])
    check = BrowserCheckResult(
        enabled=True,
        performed=True,
        pages_checked=1,
        items=[BrowserPageResult(browser_check_performed=True, url="https://example.ru")],
        cookie_interaction=result,
    )

    from app.analyzers.cookie_analyzer import CookieAnalyzer

    cookies = CookieAnalyzer().analyze(check)

    assert cookies.reject_button_found is False
    assert "Явная кнопка отклонения cookie" in " ".join(cookies.warnings)


def test_cookie_interaction_reject_reduces_cookies() -> None:
    result = interaction_result(
        buttons=[button("Отклонить", "reject")],
        reject_clicked=True,
        cookies_reduced=True,
        analytics_reduced=True,
        advertising_reduced=True,
    )

    assert result.reject_clicked is True
    assert result.cookies_reduced_after_reject is True


def test_cookie_interaction_warns_when_analytics_not_reduced() -> None:
    result = interaction_result(
        buttons=[button("Отклонить", "reject")],
        reject_clicked=True,
        cookies_reduced=True,
        analytics_reduced=False,
        advertising_reduced=True,
    )
    check = BrowserCheckResult(
        enabled=True,
        performed=True,
        pages_checked=1,
        items=[BrowserPageResult(browser_check_performed=True, url="https://example.ru")],
        cookie_interaction=result,
    )

    from app.analyzers.cookie_analyzer import CookieAnalyzer

    cookies = CookieAnalyzer().analyze(check)

    assert cookies.analytics_reduced_after_reject is False
    assert "не уменьшилось" in " ".join(cookies.warnings)


def test_risk_service_adds_reject_button_not_found_factor() -> None:
    result = RiskService().assess(
        cookies=CookieAnalysisResult(
            browser_check_available=True,
            analyzed=True,
            banner_found=True,
            cookies_before_consent_found=True,
            reject_button_found=False,
        ),
        check=make_check(),
    )

    assert "cookie_reject_button_not_found" in factor_codes(result)


def test_risk_service_adds_reject_did_not_reduce_tracking_factor() -> None:
    result = RiskService().assess(
        cookies=CookieAnalysisResult(
            browser_check_available=True,
            analyzed=True,
            reject_test_performed=True,
            analytics_reduced_after_reject=False,
        ),
        check=make_check(),
    )

    assert "cookie_reject_did_not_reduce_tracking" in factor_codes(result)


def test_report_mentions_reject_button_not_found() -> None:
    report = ReportService().build(
        make_check_result(
            cookies=CookieAnalysisResult(
                browser_check_available=True,
                analyzed=True,
                interaction_available=True,
                cookies_before_consent_found=True,
                reject_button_found=False,
            )
        )
    )

    assert "Явная кнопка отклонения cookie не была найдена автоматически" in report.summary


def test_report_mentions_tracking_not_reduced_after_reject() -> None:
    report = ReportService().build(
        make_check_result(
            cookies=CookieAnalysisResult(
                browser_check_available=True,
                analyzed=True,
                reject_test_performed=True,
                analytics_reduced_after_reject=False,
            )
        )
    )

    assert "не зафиксировано заметного снижения cookies или запросов" in report.summary


@pytest.mark.asyncio
async def test_check_service_keeps_old_response_when_browser_disabled() -> None:
    service = CheckService(
        availability_service=FakeAvailabilityService(),
        crawl_service=FakeCrawlService(),
        browser_check_service=FakeBrowserCheckService(enabled=False),
    )

    result = await service.check("https://example.ru")

    assert result.browser_check is None
    assert result.cookies is None


@pytest.mark.asyncio
async def test_check_service_includes_cookie_interaction_when_enabled() -> None:
    service = CheckService(
        availability_service=FakeAvailabilityService(),
        crawl_service=FakeCrawlService(),
        browser_check_service=FakeBrowserCheckService(
            enabled=True,
            interaction=interaction_result(buttons=[button("Отклонить", "reject")]),
        ),
    )

    result = await service.check("https://example.ru")

    assert result.browser_check is not None
    assert result.browser_check.cookie_interaction is not None
    assert result.cookies is not None
    assert result.cookies.interaction_available is True
