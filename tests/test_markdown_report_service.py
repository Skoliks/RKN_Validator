from datetime import UTC, datetime

from app.schemas.accessibility import AccessibilityAnalysisResult
from app.schemas.advertising import AdvertisingAnalysisResult
from app.schemas.availability import AvailabilityInfo
from app.schemas.browser import BrowserCheckResult, BrowserPageResult
from app.schemas.check import CheckMeta, CheckResult
from app.schemas.cookies import CookieAnalysisResult
from app.schemas.domain_compliance import DomainComplianceResult
from app.schemas.infrastructure import InfrastructureAnalysisResult, InfrastructureDomainItem
from app.schemas.owner_requisites import OwnerRequisitesResult
from app.schemas.pages import PageItem, PagesResult
from app.schemas.report import ReportResult
from app.schemas.risk import RiskAssessment, RiskFactor
from app.schemas.security import SecurityResult
from app.schemas.site import SiteInfo
from app.services.markdown_report_service import MarkdownReportService


FORBIDDEN_PHRASES = [
    "сайт нарушает закон",
    "сайт незаконен",
    "нарушение 152-фз",
    "нарушение закона о рекламе",
    "данные хранятся за границей",
    "сайт не соответствует гост",
    "реклама оформлена неправильно",
    "согласие отсутствует",
]


def make_result(risk_factors: list[RiskFactor] | None = None) -> CheckResult:
    return CheckResult(
        site=SiteInfo(
            original_input="example.com",
            normalized_url="https://example.com",
            final_url="https://example.com",
            domain="example.com",
            domain_zone="com",
        ),
        check=CheckMeta(
            status="completed",
            checked_at=datetime(2026, 7, 1, tzinfo=UTC),
            duration_ms=123,
            mode="sync",
            interface="api",
        ),
        availability=AvailabilityInfo(available=True, status_code=200),
        browser_check=BrowserCheckResult(
            enabled=True,
            performed=True,
            pages_checked=1,
            items=[
                BrowserPageResult(
                    browser_check_performed=True,
                    url="https://example.com",
                    visible_text="VISIBLE_TEXT_SHOULD_NOT_BE_EXPORTED",
                )
            ],
        ),
        cookies=CookieAnalysisResult(
            browser_check_available=True,
            analyzed=True,
            banner_found=False,
            cookies_before_consent_found=False,
            third_party_cookies_before_consent_found=False,
            analytics_requests_before_consent_found=False,
            advertising_requests_before_consent_found=False,
            third_party_requests_before_consent_found=False,
        ),
        advertising=AdvertisingAnalysisResult(found=False),
        accessibility=AccessibilityAnalysisResult(
            checked=True,
            issues_found=True,
            missing_alt_count=1,
            empty_links_count=2,
            missing_input_labels_count=3,
            iframe_missing_title_count=4,
            duplicate_ids_count=5,
        ),
        infrastructure=InfrastructureAnalysisResult(
            checked=True,
            domains_count=2,
            external_domains_found=True,
            foreign_services_found=True,
            analytics_services_found=True,
            domains=[
                InfrastructureDomainItem(
                    domain="cdn.example.net",
                    category="cdn",
                    is_third_party=True,
                    source="html",
                )
            ],
        ),
        owner_requisites=OwnerRequisitesResult(
            found=True,
            organization_name="ООО Ромашка",
            inn="7700000000",
            ogrn="1027700000000",
            phone_found=True,
            email_found=True,
            address_found=True,
            privacy_email_found=False,
        ),
        domain_compliance=DomainComplianceResult(
            zone="com",
            applies_to_domain_zone=False,
            esia_identification_required=False,
            status="not_applicable",
            message="Требование к зоне не применяется.",
        ),
        security=SecurityResult(https_enabled=True, has_mixed_content=False),
        pages=PagesResult(
            total_found=1,
            total_checked=1,
            items=[PageItem(url="https://example.com", status_code=200)],
        ),
        risk_assessment=RiskAssessment(
            total_score=25 if risk_factors else 0,
            level="low",
            factors=risk_factors or [],
        ),
        report=ReportResult(
            summary=["Сайт был доступен.", "Проверено 1 страница."],
            recommendations=["Периодически повторять проверку."],
            recommendation="Периодически повторять проверку.",
            checked_areas=["Доступность сайта", "Cookie и сетевые запросы"],
            manual_review_required=["Политика и согласия."],
            limitations=["Автоматическая проверка не является юридическим заключением."],
            llm_generated=False,
        ),
    )


def test_markdown_report_service_returns_markdown_with_required_sections() -> None:
    factor = RiskFactor(
        code="cookies_before_consent_detected",
        level="medium",
        score=20,
        message="Обнаружены признаки cookies до выбора пользователя.",
        evidence=["<script>bad</script>", "data:image/png;base64," + ("A" * 400)],
    )

    markdown = MarkdownReportService().build(make_result([factor]))

    assert isinstance(markdown, str)
    assert "# Отчёт по проверке сайта" in markdown
    assert "**Сайт:** https://example.com" in markdown
    assert "**Домен:** example.com" in markdown
    assert "**Статус проверки:** completed" in markdown
    assert "**Уровень риска:** low" in markdown
    assert "## Краткие выводы" in markdown
    assert "## Рекомендации" in markdown
    assert "## Что проверялось автоматически" in markdown
    assert "## Что требует ручной проверки" in markdown
    assert "## Ограничения проверки" in markdown
    assert "| medium | cookies_before_consent_detected |" in markdown
    assert "## Cookie и согласия" in markdown
    assert "## Реклама" in markdown
    assert "## Доступность" in markdown
    assert "## Инфраструктура и сторонние сервисы" in markdown
    assert "## Реквизиты владельца" in markdown
    assert "## Доменная зона" in markdown
    assert "## Технические детали" in markdown


def test_markdown_report_service_omits_large_or_sensitive_raw_content() -> None:
    markdown = MarkdownReportService().build(
        make_result(
            [
                RiskFactor(
                    code="example",
                    level="low",
                    score=5,
                    message="Example",
                    evidence=[
                        "<html><body>VISIBLE_HTML_SHOULD_NOT_BE_EXPORTED</body></html>",
                        "data:image/png;base64," + ("A" * 500),
                    ],
                )
            ]
        )
    )

    assert "VISIBLE_TEXT_SHOULD_NOT_BE_EXPORTED" not in markdown
    assert "<html" not in markdown.lower()
    assert "<body" not in markdown.lower()
    assert "data:image" not in markdown.lower()
    assert "base64" not in markdown.lower()
    assert "A" * 120 not in markdown


def test_markdown_report_service_has_neutral_phrase_when_no_risk_factors() -> None:
    markdown = MarkdownReportService().build(make_result())

    assert "Существенные риск-факторы автоматически не обнаружены." in markdown
    assert "cookie-баннер не был найден" not in markdown.lower()


def test_markdown_report_service_avoids_forbidden_legal_phrases() -> None:
    markdown = MarkdownReportService().build(make_result()).lower()

    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in markdown


def test_markdown_report_service_requires_manual_owner_check_without_organization() -> None:
    result = make_result()
    result.owner_requisites = OwnerRequisitesResult(
        found=True,
        organization_name=None,
        manual_check_required=True,
        warnings=[
            "На проверенных страницах обнаружены разные упоминания организаций; требуется ручная проверка владельца сайта."
        ],
    )

    markdown = MarkdownReportService().build(result)

    assert "Организация: требуется ручная проверка" in markdown
    assert "ООО «Газпром переработка Благовещенск»" not in markdown


def test_markdown_report_service_deduplicates_cookie_warnings() -> None:
    result = make_result()
    result.cookies = CookieAnalysisResult(
        browser_check_available=True,
        analyzed=True,
        banner_found=True,
        reject_button_found=False,
        warnings=[
            "Найден cookie-баннер, но явная кнопка отклонения не была найдена автоматически.",
            "Найден cookie-баннер, но явная кнопка отклонения не была найдена автоматически.",
        ],
    )

    markdown = MarkdownReportService().build(result)

    assert markdown.count("Найден cookie-баннер") == 1
