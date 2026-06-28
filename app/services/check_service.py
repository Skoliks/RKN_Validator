from datetime import UTC, datetime
from time import perf_counter

from app.analyzers import (
    AuthProviderAnalyzer,
    ConsentAnalyzer,
    DomainComplianceAnalyzer,
    ExternalServicesAnalyzer,
    FormAnalyzer,
    HttpsAnalyzer,
    OwnerRequisitesAnalyzer,
    PolicyAnalyzer,
    RussianMarketAnalyzer,
)
from app.core.exceptions import InvalidUrlError, InvalidUserInputError
from app.schemas.availability import AvailabilityInfo
from app.schemas.check import CheckMeta, CheckResult
from app.schemas.domain_compliance import DomainComplianceResult
from app.schemas.pages import PageData, PageItem, PagesResult
from app.schemas.site import SiteInfo
from app.services.availability_service import AvailabilityService, UNAVAILABLE_MESSAGE
from app.services.crawl_service import CrawlService
from app.services.report_service import ReportService
from app.services.risk_service import RiskService
from app.services.url_service import UrlService


class CheckService:
    def __init__(
        self,
        url_service: UrlService | None = None,
        availability_service: AvailabilityService | None = None,
        crawl_service: CrawlService | None = None,
        form_analyzer: FormAnalyzer | None = None,
        consent_analyzer: ConsentAnalyzer | None = None,
        policy_analyzer: PolicyAnalyzer | None = None,
        domain_compliance_analyzer: DomainComplianceAnalyzer | None = None,
        external_services_analyzer: ExternalServicesAnalyzer | None = None,
        auth_provider_analyzer: AuthProviderAnalyzer | None = None,
        https_analyzer: HttpsAnalyzer | None = None,
        owner_requisites_analyzer: OwnerRequisitesAnalyzer | None = None,
        russian_market_analyzer: RussianMarketAnalyzer | None = None,
        risk_service: RiskService | None = None,
        report_service: ReportService | None = None,
    ) -> None:
        self.url_service = url_service or UrlService()
        self.availability_service = availability_service or AvailabilityService()
        self.crawl_service = crawl_service or CrawlService()
        self.form_analyzer = form_analyzer or FormAnalyzer()
        self.consent_analyzer = consent_analyzer or ConsentAnalyzer()
        self.policy_analyzer = policy_analyzer or PolicyAnalyzer()
        self.domain_compliance_analyzer = domain_compliance_analyzer or DomainComplianceAnalyzer()
        self.external_services_analyzer = external_services_analyzer or ExternalServicesAnalyzer()
        self.auth_provider_analyzer = auth_provider_analyzer or AuthProviderAnalyzer()
        self.https_analyzer = https_analyzer or HttpsAnalyzer()
        self.owner_requisites_analyzer = owner_requisites_analyzer or OwnerRequisitesAnalyzer()
        self.russian_market_analyzer = russian_market_analyzer or RussianMarketAnalyzer()
        self.risk_service = risk_service or RiskService()
        self.report_service = report_service or ReportService()

    async def check(self, user_url: str) -> CheckResult:
        started_at = perf_counter()

        try:
            site = self.url_service.normalize(user_url)
        except InvalidUserInputError as exc:
            return self._failed_result(
                user_url=user_url,
                error_type=exc.code,
                message=str(exc),
                started_at=started_at,
            )
        except InvalidUrlError as exc:
            return self._failed_result(
                user_url=user_url,
                error_type=exc.code,
                message=str(exc),
                started_at=started_at,
            )

        availability = await self.availability_service.check(site)
        domain_compliance = self.domain_compliance_analyzer.analyze(site)
        if not availability.available:
            failed_availability = AvailabilityInfo(
                available=False,
                status_code=availability.status_code,
                error_type="site_unavailable",
                message=availability.message or UNAVAILABLE_MESSAGE,
            )
            return self._failed_result(
                user_url=user_url,
                error_type="site_unavailable",
                message=failed_availability.message or UNAVAILABLE_MESSAGE,
                started_at=started_at,
                site=site,
                availability=failed_availability,
                domain_compliance=domain_compliance,
            )

        crawl = await self.crawl_service.crawl(site)
        pages_data = crawl.pages

        forms = self.form_analyzer.analyze(pages_data)
        consents = self.consent_analyzer.analyze(pages_data, forms)
        policy = self.policy_analyzer.analyze(pages_data)
        external_services = self.external_services_analyzer.analyze(pages_data)
        authentication = self.auth_provider_analyzer.analyze(pages_data)
        security = self.https_analyzer.analyze(pages_data, forms)
        owner_requisites = self.owner_requisites_analyzer.analyze(pages_data)
        russian_market = self.russian_market_analyzer.analyze(pages_data)

        status = "partial" if crawl.warnings else "completed"
        check_meta = self._check_meta(status=status, started_at=started_at)
        risk_assessment = self.risk_service.assess(
            forms=forms,
            consents=consents,
            policy=policy,
            external_services=external_services,
            authentication=authentication,
            security=security,
            check=check_meta,
        )
        result = CheckResult(
            site=site,
            check=check_meta,
            availability=availability,
            domain_compliance=domain_compliance,
            pages=self._to_pages_result(pages_data),
            owner_requisites=owner_requisites,
            russian_market=russian_market,
            forms=forms,
            consents=consents,
            policy=policy,
            external_services=external_services,
            authentication=authentication,
            security=security,
            risk_assessment=risk_assessment,
        )
        report = self.report_service.build(result)
        return result.model_copy(update={"report": report})

    def _failed_result(
        self,
        user_url: str,
        error_type: str,
        message: str,
        started_at: float,
        site: SiteInfo | None = None,
        availability: AvailabilityInfo | None = None,
        domain_compliance: DomainComplianceResult | None = None,
    ) -> CheckResult:
        failed_site = site or SiteInfo(
            original_input=user_url,
            normalized_url="",
            final_url=None,
            domain="",
            domain_zone=None,
        )
        failed_availability = availability or AvailabilityInfo(
            available=False,
            error_type=error_type,
            message=message,
        )
        result = CheckResult(
            site=failed_site,
            check=self._check_meta(status="failed", started_at=started_at),
            availability=failed_availability,
            domain_compliance=domain_compliance,
        )
        report = self.report_service.build(result)
        return result.model_copy(update={"report": report})

    def _check_meta(self, status: str, started_at: float) -> CheckMeta:
        return CheckMeta(
            status=status,
            checked_at=datetime.now(UTC),
            duration_ms=max(int((perf_counter() - started_at) * 1000), 0),
            mode="sync",
            interface="api",
        )

    def _to_pages_result(self, pages: list[PageData]) -> PagesResult:
        return PagesResult(
            total_found=len(pages),
            total_checked=len(pages),
            items=[
                PageItem(
                    url=page.url,
                    final_url=page.final_url,
                    status_code=page.status_code,
                    title=page.title,
                    content_type=page.content_type,
                )
                for page in pages
            ],
        )
