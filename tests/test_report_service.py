from datetime import UTC, datetime

from app.schemas.availability import AvailabilityInfo
from app.schemas.check import CheckMeta, CheckResult
from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.forms import FormField, FormItem, FormsResult
from app.schemas.pages import PageItem, PagesResult
from app.schemas.policy import PolicyResult
from app.schemas.report import ReportResult
from app.schemas.risk import RiskAssessment, RiskFactor
from app.schemas.site import SiteInfo
from app.services.report_service import ReportService


def make_check_result(
    status: str = "completed",
    risk_level: str = "low",
    risk_score: int = 0,
    factors: list[RiskFactor] | None = None,
    availability: AvailabilityInfo | None = None,
    forms: FormsResult | None = None,
    policy: PolicyResult | None = None,
    external_services: ExternalServicesResult | None = None,
) -> CheckResult:
    return CheckResult(
        site=SiteInfo(
            original_input="example.ru",
            normalized_url="https://example.ru",
            final_url="https://example.ru",
            domain="example.ru",
            domain_zone="ru",
        ),
        check=CheckMeta(
            status=status,
            checked_at=datetime.now(UTC),
            duration_ms=100,
            mode="sync",
            interface="api",
        ),
        availability=availability or AvailabilityInfo(available=True, status_code=200),
        pages=PagesResult(
            total_found=1,
            total_checked=1,
            items=[PageItem(url="https://example.ru", status_code=200)],
        ),
        forms=forms if forms is not None else FormsResult(),
        policy=policy if policy is not None else PolicyResult(found=True, policy_url="https://example.ru/privacy"),
        external_services=external_services or ExternalServicesResult(),
        risk_assessment=RiskAssessment(
            total_score=risk_score,
            level=risk_level,
            factors=factors or [],
        ),
    )


def test_report_low_risk() -> None:
    report = ReportService().build(make_check_result())

    assert isinstance(report, ReportResult)
    assert report.llm_generated is False
    assert "периодически повторять проверку" in report.recommendation.lower()
    assert "потенциального риска low" in report.summary


def test_report_medium_risk() -> None:
    factor = RiskFactor(
        code="foreign_analytics_detected",
        level="medium",
        score=25,
        message="Обнаружены внешние аналитические сервисы.",
        evidence=["https://www.google-analytics.com/analytics.js"],
    )
    report = ReportService().build(
        make_check_result(
            risk_level="medium",
            risk_score=45,
            factors=[factor],
            external_services=ExternalServicesResult(
                found=True,
                items=[
                    ExternalServiceItem(
                        service_type="analytics",
                        provider="Google Analytics",
                        url="https://www.google-analytics.com/analytics.js",
                    )
                ],
            ),
        )
    )

    assert "вручную проверить замечания" in report.recommendation.lower()
    assert "foreign_analytics_detected" in report.summary


def test_report_high_risk() -> None:
    factor = RiskFactor(
        code="forms_without_consent",
        level="high",
        score=35,
        message="Для части форм не обнаружены признаки согласия.",
        evidence=["contact"],
    )
    forms = FormsResult(
        found=True,
        total=1,
        items=[
            FormItem(
                form_id="contact",
                page_url="https://example.ru",
                fields=[FormField(name="phone", field_type="phone")],
            )
        ],
    )

    report = ReportService().build(
        make_check_result(
            risk_level="high",
            risk_score=90,
            factors=[factor],
            forms=forms,
            policy=PolicyResult(found=False),
        )
    )

    assert "провести ручную проверку" in report.recommendation.lower()
    assert "доработать документы, формы и сторонние сервисы" in report.recommendation.lower()


def test_report_failed_not_a_url() -> None:
    result = make_check_result(
        status="failed",
        availability=AvailabilityInfo(
            available=False,
            error_type="not_a_url",
            message="Не понял ваш запрос, пожалуйста отправьте ссылку на сайт для проверки.",
        ),
    )

    report = ReportService().build(result)

    assert "Не понял ваш запрос" in report.summary
    assert report.llm_generated is False


def test_report_failed_site_unavailable() -> None:
    result = make_check_result(
        status="failed",
        availability=AvailabilityInfo(
            available=False,
            error_type="site_unavailable",
            message="Сайт недоступен, поэтому проверку выполнить не удалось.",
        ),
    )

    report = ReportService().build(result)

    assert "Сайт недоступен, поэтому проверку выполнить не удалось." in report.summary


def test_report_partial_check() -> None:
    report = ReportService().build(make_check_result(status="partial", risk_level="medium", risk_score=35))

    assert "Проверка выполнена частично" in report.summary


def test_report_does_not_contain_forbidden_legal_phrase() -> None:
    report = ReportService().build(make_check_result(risk_level="high", risk_score=80))

    assert "сайт нарушает закон" not in report.summary.lower()
    assert "сайт нарушает закон" not in report.recommendation.lower()
