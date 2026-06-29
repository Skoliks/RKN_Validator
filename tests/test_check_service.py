import pytest
from app.schemas.browser import BrowserCheckResult, BrowserPageResult
from app.schemas.availability import AvailabilityInfo
from app.schemas.pages import CrawlResult, PageData
from app.schemas.site import SiteInfo
from app.services.availability_service import UNAVAILABLE_MESSAGE
from app.services.check_service import CheckService


class FakeAvailabilityService:
    def __init__(self, result: AvailabilityInfo) -> None:
        self.result = result

    async def check(self, site: SiteInfo) -> AvailabilityInfo:
        return self.result


class FakeCrawlService:
    def __init__(self, result: CrawlResult) -> None:
        self.result = result

    async def crawl(self, site: SiteInfo) -> CrawlResult:
        return self.result


class FakeBrowserCheckService:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.called = False

    async def check(self, pages_or_urls, source_domain: str | None = None):
        self.called = True
        if not self.enabled:
            raise AssertionError("Browser check should not be called when disabled.")
        return BrowserCheckResult(
            enabled=True,
            performed=True,
            pages_checked=1,
            items=[
                BrowserPageResult(
                    browser_check_performed=True,
                    url="https://example.ru",
                    final_url="https://example.ru",
                )
            ],
        )


def make_available() -> AvailabilityInfo:
    return AvailabilityInfo(available=True, status_code=200, message="Сайт доступен.")


def make_page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def make_service(
    availability: AvailabilityInfo | None = None,
    crawl: CrawlResult | None = None,
) -> CheckService:
    return CheckService(
        availability_service=FakeAvailabilityService(availability or make_available()),
        crawl_service=FakeCrawlService(crawl or CrawlResult(pages=[make_page('<html lang="ru"></html>')])),
        browser_check_service=FakeBrowserCheckService(enabled=False),
    )


@pytest.mark.asyncio
async def test_check_service_successful_check() -> None:
    service = make_service(
        crawl=CrawlResult(
            pages=[
                make_page(
                    """
                    <html>
                      <a href="/privacy">Политика конфиденциальности</a>
                    </html>
                    """
                )
            ]
        )
    )

    result = await service.check("example.ru")

    assert result.check.status == "completed"
    assert result.site.normalized_url == "https://example.ru"
    assert result.availability.available is True
    assert result.pages is not None
    assert result.pages.total_checked == 1
    assert result.report is not None
    assert result.report.llm_generated is False


@pytest.mark.asyncio
async def test_check_service_not_a_url() -> None:
    result = await make_service().check("какая сегодня погода")

    assert result.check.status == "failed"
    assert result.availability.error_type == "not_a_url"
    assert result.availability.message == (
        "Не понял ваш запрос, пожалуйста отправьте ссылку на сайт для проверки."
    )


@pytest.mark.asyncio
async def test_check_service_invalid_url() -> None:
    result = await make_service().check("https://")

    assert result.check.status == "failed"
    assert result.availability.error_type == "invalid_url"
    assert result.availability.message == (
        "Ссылка указана некорректно, пожалуйста отправьте адрес сайта в формате https://example.ru."
    )


@pytest.mark.asyncio
async def test_check_service_site_unavailable() -> None:
    service = make_service(
        availability=AvailabilityInfo(
            available=False,
            status_code=503,
            error_type="site_unavailable",
            message=UNAVAILABLE_MESSAGE,
        )
    )

    result = await service.check("example.ru")

    assert result.check.status == "failed"
    assert result.availability.error_type == "site_unavailable"
    assert result.availability.message == UNAVAILABLE_MESSAGE
    assert result.report is not None
    assert UNAVAILABLE_MESSAGE in result.report.summary


@pytest.mark.asyncio
async def test_check_service_site_with_form_without_policy() -> None:
    service = make_service(
        crawl=CrawlResult(
            pages=[
                make_page(
                    """
                    <form id="callback" action="/send" method="post">
                      <input name="phone" type="tel" />
                      <button>Отправить</button>
                    </form>
                    """
                )
            ]
        )
    )

    result = await service.check("example.ru")

    assert result.check.status == "completed"
    assert result.forms is not None
    assert result.forms.found is True
    assert result.policy is not None
    assert result.policy.found is False
    assert result.risk_assessment is not None
    assert result.risk_assessment.level == "high"
    assert {"privacy_policy_not_found", "forms_without_consent"}.issubset(
        {factor.code for factor in result.risk_assessment.factors}
    )


@pytest.mark.asyncio
async def test_check_service_site_with_google_tag_manager() -> None:
    service = make_service(
        crawl=CrawlResult(
            pages=[
                make_page(
                    '<html lang="ru"><script src="https://www.googletagmanager.com/gtm.js?id=GTM-123"></script></html>'
                )
            ]
        )
    )

    result = await service.check("example.ru")

    assert result.check.status == "completed"
    assert result.external_services is not None
    assert result.external_services.found is True
    assert result.risk_assessment is not None
    assert "foreign_analytics_detected" in {
        factor.code for factor in result.risk_assessment.factors
    }
    assert result.risk_assessment.level == "low"


@pytest.mark.asyncio
async def test_check_service_includes_owner_requisites() -> None:
    service = make_service(
        crawl=CrawlResult(
            pages=[
                make_page(
                    """
                    <footer>
                      ООО "ИнфоКом"
                      ИНН 2801121089
                      ОГРН 1072801006530
                    </footer>
                    """
                )
            ]
        )
    )

    result = await service.check("example.ru")

    assert result.owner_requisites is not None
    assert result.owner_requisites.found is True
    assert result.owner_requisites.organization_name == 'ООО "ИнфоКом"'
    assert result.owner_requisites.inn == "2801121089"
    assert result.owner_requisites.ogrn == "1072801006530"
    assert "<footer>" not in str(result.model_dump())


@pytest.mark.asyncio
async def test_check_service_includes_domain_compliance_for_ru_zone() -> None:
    result = await make_service().check("https://example.ru")

    assert result.domain_compliance is not None
    assert result.domain_compliance.zone == "ru"
    assert result.domain_compliance.applies_to_domain_zone is True
    assert result.domain_compliance.esia_identification_required is True
    assert result.domain_compliance.status == "applicable_requires_manual_check"
    assert result.risk_assessment is not None
    assert result.risk_assessment.total_score == 0
    assert result.risk_assessment.factors == []


@pytest.mark.asyncio
async def test_check_service_includes_domain_compliance_for_io_zone() -> None:
    result = await make_service().check("https://infocom.io")

    assert result.domain_compliance is not None
    assert result.domain_compliance.zone == "io"
    assert result.domain_compliance.applies_to_domain_zone is False
    assert result.domain_compliance.esia_identification_required is False
    assert result.domain_compliance.status == "not_applicable"


@pytest.mark.asyncio
async def test_check_service_does_not_call_browser_check_when_disabled() -> None:
    browser_check_service = FakeBrowserCheckService(enabled=False)
    service = CheckService(
        availability_service=FakeAvailabilityService(make_available()),
        crawl_service=FakeCrawlService(CrawlResult(pages=[make_page('<html lang="ru"></html>')])),
        browser_check_service=browser_check_service,
    )

    result = await service.check("https://example.ru")

    assert browser_check_service.called is False
    assert result.browser_check is None


@pytest.mark.asyncio
async def test_check_service_includes_browser_check_when_enabled() -> None:
    browser_check_service = FakeBrowserCheckService(enabled=True)
    service = CheckService(
        availability_service=FakeAvailabilityService(make_available()),
        crawl_service=FakeCrawlService(CrawlResult(pages=[make_page('<html lang="ru"></html>')])),
        browser_check_service=browser_check_service,
    )

    result = await service.check("https://example.ru")

    assert browser_check_service.called is True
    assert result.browser_check is not None
    assert result.browser_check.performed is True


def test_check_result_pages_do_not_contain_html() -> None:
    page = make_page("<form><input name='phone'></form>")
    result = CheckService()._to_pages_result([page])

    dumped = result.model_dump()
    assert "html" not in str(dumped)
