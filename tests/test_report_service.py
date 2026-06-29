from datetime import UTC, datetime

from app.schemas.accessibility import AccessibilityAnalysisResult
from app.schemas.advertising import AdvertisingAnalysisResult, AdvertisingServiceItem
from app.schemas.availability import AvailabilityInfo
from app.schemas.browser import BrowserCheckResult, CookieInteractionResult
from app.schemas.check import CheckMeta, CheckResult
from app.schemas.cookies import CookieAnalysisResult
from app.schemas.domain_compliance import DomainComplianceResult
from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.forms import FormField, FormItem, FormsResult
from app.schemas.infrastructure import InfrastructureAnalysisResult
from app.schemas.owner_requisites import OwnerRequisitesResult
from app.schemas.pages import PageItem, PagesResult
from app.schemas.policy import PolicyMatchedLink, PolicyResult
from app.schemas.report import ReportResult
from app.schemas.risk import RiskAssessment, RiskFactor
from app.schemas.security import SecurityResult
from app.schemas.site import SiteInfo
from app.services.report_service import ReportService


def summary_text(report) -> str:
    return " ".join(report.summary)


def make_check_result(
    status: str = "completed",
    risk_level: str = "low",
    risk_score: int = 0,
    factors: list[RiskFactor] | None = None,
    availability: AvailabilityInfo | None = None,
    domain_compliance: DomainComplianceResult | None = None,
    cookies: CookieAnalysisResult | None = None,
    advertising: AdvertisingAnalysisResult | None = None,
    accessibility: AccessibilityAnalysisResult | None = None,
    infrastructure: InfrastructureAnalysisResult | None = None,
    browser_check: BrowserCheckResult | None = None,
    forms: FormsResult | None = None,
    owner_requisites: OwnerRequisitesResult | None = None,
    policy: PolicyResult | None = None,
    external_services: ExternalServicesResult | None = None,
    security: SecurityResult | None = None,
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
        domain_compliance=domain_compliance,
        browser_check=browser_check,
        cookies=cookies,
        advertising=advertising,
        accessibility=accessibility,
        infrastructure=infrastructure,
        pages=PagesResult(
            total_found=4,
            total_checked=4,
            items=[PageItem(url="https://example.ru", status_code=200)],
        ),
        forms=forms if forms is not None else FormsResult(),
        owner_requisites=owner_requisites,
        policy=policy
        if policy is not None
        else PolicyResult(found=True, policy_url="https://example.ru/privacy"),
        external_services=external_services or ExternalServicesResult(),
        security=security,
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
    assert "низкий уровень потенциального риска" in summary_text(report)
    assert "Проверено 4 страницы" in summary_text(report)


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

    assert "сторонних сервисов" in report.recommendation.lower()
    assert "foreign_analytics_detected" not in summary_text(report)
    assert "сторонних сервисов" in report.recommendation.lower()


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

    assert "политики конфиденциальности" in report.recommendation.lower()


def test_report_failed_not_a_url() -> None:
    message = "Не понял запрос, пожалуйста отправьте ссылку на сайт для проверки."
    result = make_check_result(
        status="failed",
        availability=AvailabilityInfo(
            available=False,
            error_type="not_a_url",
            message=message,
        ),
    )

    report = ReportService().build(result)

    assert message in summary_text(report)
    assert report.llm_generated is False


def test_report_failed_site_unavailable() -> None:
    message = "Сайт недоступен, поэтому проверку выполнить не удалось."
    result = make_check_result(
        status="failed",
        availability=AvailabilityInfo(
            available=False,
            error_type="site_unavailable",
            message=message,
        ),
    )

    report = ReportService().build(result)

    assert message in summary_text(report)


def test_report_partial_check() -> None:
    report = ReportService().build(
        make_check_result(status="partial", risk_level="medium", risk_score=35)
    )

    assert "Проверка выполнена частично" in summary_text(report)


def test_report_does_not_contain_forbidden_legal_phrase() -> None:
    report = ReportService().build(make_check_result(risk_level="high", risk_score=80))

    assert "сайт нарушает закон" not in summary_text(report).lower()
    assert "сайт нарушает закон" not in report.recommendation.lower()


def test_report_translates_low_to_russian() -> None:
    report = ReportService().build(make_check_result(risk_level="low"))

    assert "низкий" in summary_text(report)


def test_report_does_not_say_policy_missing_when_privacy_document_found() -> None:
    report = ReportService().build(
        make_check_result(
            policy=PolicyResult(
                found=True,
                policy_url="https://infocom.io/waba-privacy-ru",
                matched_links=[
                    PolicyMatchedLink(
                        page_url="https://infocom.io",
                        href="https://infocom.io/waba-privacy-ru",
                        text="Условия конфиденциальности",
                    )
                ],
            )
        )
    )

    assert "не найдена" not in summary_text(report).lower()


def test_report_uses_cautious_privacy_document_wording() -> None:
    report = ReportService().build(make_check_result())

    assert "Политика конфиденциальности" in report.checked_areas
    assert "Найдена ссылка на политику обработки персональных данных" not in summary_text(report)


def test_report_mentions_applicable_domain_compliance() -> None:
    report = ReportService().build(
        make_check_result(
            domain_compliance=DomainComplianceResult(
                zone="ru",
                esia_identification_required=True,
                applies_to_domain_zone=True,
                manual_check_required=True,
                status="applicable_requires_manual_check",
            )
        )
    )

    assert "Доменная зона" in report.checked_areas
    assert "идентификация не пройдена" not in summary_text(report).lower()


def test_report_mentions_not_applicable_domain_compliance() -> None:
    report = ReportService().build(
        make_check_result(
            domain_compliance=DomainComplianceResult(
                zone="io",
                status="not_applicable",
            )
        )
    )

    assert (
        "Требование идентификации администратора через ЕСИА к данной доменной зоне "
        "не применяется."
    ) in summary_text(report)


def test_report_mentions_found_owner_inn_and_ogrn() -> None:
    report = ReportService().build(
        make_check_result(
            owner_requisites=OwnerRequisitesResult(
                found=True,
                organization_name='ООО "ИнфоКом"',
                inn="2801121089",
                ogrn="1072801006530",
            )
        )
    )

    assert "На проверенных страницах обнаружены реквизиты владельца сайта." in summary_text(report)


def test_report_recommends_checking_privacy_email_when_missing() -> None:
    report = ReportService().build(
        make_check_result(
            owner_requisites=OwnerRequisitesResult(
                found=True,
                organization_name='ООО "ИнфоКом"',
                inn="2801121089",
                ogrn="1072801006530",
                privacy_email_found=False,
            )
        )
    )

    assert "отдельного контактного адреса" in report.recommendation


def test_report_mentions_mixed_content_without_risk_escalation() -> None:
    report = ReportService().build(
        make_check_result(
            owner_requisites=OwnerRequisitesResult(
                found=True,
                organization_name='ООО "ИнфоКом"',
                inn="2801121089",
                ogrn="1072801006530",
            ),
            external_services=ExternalServicesResult(
                found=True,
                items=[
                    ExternalServiceItem(
                        service_type="cdn",
                        provider="UNPKG",
                        url="https://unpkg.com/library.js",
                        foreign=True,
                    )
                ],
            ),
            security=SecurityResult(https_enabled=True, has_mixed_content=True),
        )
    )

    assert (
        "Обнаружены признаки смешанного содержимого: часть ресурсов запрашивается по небезопасному HTTP."
    ) in summary_text(report)


def test_report_mentions_cookies_before_user_choice_cautiously() -> None:
    report = ReportService().build(
        make_check_result(
            cookies=CookieAnalysisResult(
                browser_check_available=True,
                analyzed=True,
                banner_found=False,
                cookies_before_consent_found=True,
                third_party_cookies_before_consent_found=True,
                analytics_requests_before_consent_found=True,
                advertising_requests_before_consent_found=True,
            )
        )
    )

    assert (
        "На момент браузерной проверки обнаружены cookies после первичной загрузки "
        "страницы до явного выбора пользователя."
    ) in summary_text(report)
    assert "Назначение cookies и сторонних сетевых запросов." in report.manual_review_required
    assert "Cookie-баннер не был найден или не был распознан автоматически" in summary_text(report)
    assert "нарушает закон" not in summary_text(report).lower()
    assert "согласие отсутствует" not in summary_text(report).lower()
    assert "обработка незаконна" not in summary_text(report).lower()


def test_report_summary_includes_advertising_block_before_truncation() -> None:
    report = ReportService().build(
        make_check_result(
            risk_level="medium",
            risk_score=55,
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
            cookies=CookieAnalysisResult(
                browser_check_available=True,
                analyzed=True,
                banner_found=False,
                cookies_before_consent_found=True,
                analytics_requests_before_consent_found=True,
                advertising_requests_before_consent_found=True,
            ),
        )
    )

    assert "Обнаружены признаки подключения рекламных сервисов." in summary_text(report)
    assert (
        "На проверенных страницах не найден erid; требуется ручная проверка рекламных материалов."
        in summary_text(report)
    )
    assert "Явная маркировка рекламы не была найдена автоматически." in summary_text(report)
    assert "сайт нарушает закон" not in summary_text(report).lower()
    assert "реклама оформлена неправильно" not in summary_text(report).lower()
    assert "сайт не соответствует закону о рекламе" not in summary_text(report).lower()


def test_report_keeps_cookie_phrases_with_infrastructure() -> None:
    report = ReportService().build(
        make_check_result(
            risk_level="medium",
            risk_score=65,
            cookies=CookieAnalysisResult(
                browser_check_available=True,
                analyzed=True,
                banner_found=False,
                cookies_before_consent_found=True,
                analytics_requests_before_consent_found=True,
                advertising_requests_before_consent_found=True,
            ),
            infrastructure=InfrastructureAnalysisResult(
                checked=True,
                external_domains_found=True,
                foreign_services_found=True,
                analytics_services_found=True,
            ),
            factors=[
                RiskFactor(
                    code="cookies_before_consent_detected",
                    level="medium",
                    score=25,
                    message="Обнаружены признаки cookies до выбора пользователя.",
                ),
                RiskFactor(
                    code="foreign_infrastructure_services_detected",
                    level="medium",
                    score=20,
                    message="Обнаружены признаки использования иностранных инфраструктурных сервисов.",
                ),
            ],
        )
    )

    assert (
        "На момент браузерной проверки обнаружены cookies после первичной загрузки страницы "
        "до явного выбора пользователя."
    ) in summary_text(report)
    assert (
        "Cookie-баннер не был найден или не был распознан автоматически; требуется ручная проверка."
    ) in summary_text(report)
    assert "Обнаружены сторонние домены и внешние инфраструктурные сервисы." in summary_text(report)
    assert (
        "Обнаружены признаки использования иностранных сервисов; требуется ручная проверка условий "
        "передачи и обработки данных."
    ) in summary_text(report)
    assert "cookie-баннер" in report.recommendation.lower()


def test_report_keeps_advertising_phrases_with_infrastructure() -> None:
    report = ReportService().build(
        make_check_result(
            risk_level="medium",
            risk_score=75,
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
            infrastructure=InfrastructureAnalysisResult(
                checked=True,
                external_domains_found=True,
                foreign_services_found=True,
                advertising_services_found=True,
            ),
            factors=[
                RiskFactor(
                    code="advertising_service_without_erid",
                    level="medium",
                    score=20,
                    message="Обнаружены признаки рекламных сервисов без найденного erid.",
                ),
                RiskFactor(
                    code="foreign_infrastructure_services_detected",
                    level="medium",
                    score=20,
                    message="Обнаружены признаки использования иностранных инфраструктурных сервисов.",
                ),
            ],
        )
    )

    assert (
        "На проверенных страницах не найден erid; требуется ручная проверка рекламных материалов."
    ) in summary_text(report)
    assert "Явная маркировка рекламы не была найдена автоматически." in summary_text(report)
    assert "Обнаружены сторонние домены и внешние инфраструктурные сервисы." in summary_text(report)
    assert (
        "Обнаружены признаки использования иностранных сервисов; требуется ручная проверка условий "
        "передачи и обработки данных."
    ) in summary_text(report)
    assert "рекламные материалы" in report.recommendation.lower()
    assert "сторонних сервисов" in report.recommendation.lower()


def test_report_adds_infrastructure_phrases_without_duplicates() -> None:
    report = ReportService().build(
        make_check_result(
            infrastructure=InfrastructureAnalysisResult(
                checked=True,
                external_domains_found=True,
                foreign_services_found=True,
            )
        )
    )

    external_phrase = "Обнаружены сторонние домены и внешние инфраструктурные сервисы."
    foreign_phrase = (
        "Обнаружены признаки использования иностранных сервисов; требуется ручная проверка условий "
        "передачи и обработки данных."
    )

    assert external_phrase in summary_text(report)
    assert foreign_phrase in summary_text(report)
    assert summary_text(report).count(external_phrase) == 1
    assert summary_text(report).count(foreign_phrase) == 1


def test_report_contains_structured_final_fields() -> None:
    report = ReportService().build(make_check_result())

    assert isinstance(report.summary, list)
    assert isinstance(report.recommendations, list)
    assert isinstance(report.checked_areas, list)
    assert isinstance(report.manual_review_required, list)
    assert isinstance(report.limitations, list)
    assert "Доступность сайта" in report.checked_areas


def test_report_limitations_mentions_browser_when_browser_check_disabled() -> None:
    report = ReportService().build(make_check_result())

    assert (
        "Браузерная проверка не выполнялась, поэтому cookies, динамические запросы и часть сторонних сервисов могли быть не обнаружены."
        in report.limitations
    )
    assert (
        "Браузерная проверка может отличаться в зависимости от региона, устройства, сессии и состояния сайта."
        not in report.limitations
    )


def test_report_checked_areas_include_browser_when_browser_check_performed() -> None:
    report = ReportService().build(
        make_check_result(
            browser_check=BrowserCheckResult(
                enabled=True,
                performed=True,
                pages_checked=1,
                cookie_interaction=CookieInteractionResult(
                    enabled=True,
                    performed=True,
                    banner_found=False,
                    reject_clicked=False,
                    accept_clicked=False,
                ),
            )
        )
    )

    assert "Браузерная проверка страницы" in report.checked_areas
    assert "Cookie и сетевые запросы до явного выбора пользователя" in report.checked_areas
    assert "Cookie interaction check" in report.checked_areas
    assert (
        "Браузерная проверка может отличаться в зависимости от региона, устройства, сессии и состояния сайта."
        in report.limitations
    )
    assert (
        "Браузерная проверка не выполнялась, поэтому cookies, динамические запросы и часть сторонних сервисов могли быть не обнаружены."
        not in report.limitations
    )


def test_report_summary_is_deduped_and_limited() -> None:
    report = ReportService().build(
        make_check_result(
            cookies=CookieAnalysisResult(
                browser_check_available=True,
                analyzed=True,
                banner_found=False,
                cookies_before_consent_found=True,
            ),
            advertising=AdvertisingAnalysisResult(
                found=True,
                ad_services_found=True,
                erid_found=False,
                ad_marking_found=False,
            ),
            accessibility=AccessibilityAnalysisResult(
                checked=True,
                issues_found=True,
                missing_alt_count=1,
            ),
            infrastructure=InfrastructureAnalysisResult(
                checked=True,
                external_domains_found=True,
                foreign_services_found=True,
            ),
            security=SecurityResult(https_enabled=True, has_mixed_content=True),
            owner_requisites=OwnerRequisitesResult(found=True, privacy_email_found=False),
            domain_compliance=DomainComplianceResult(zone="io", status="not_applicable"),
        )
    )

    assert len(report.summary) <= 12
    assert len(report.summary) == len(set(report.summary))


def test_report_recommendations_do_not_include_irrelevant_items() -> None:
    report = ReportService().build(make_check_result())

    text = " ".join(report.recommendations).lower()

    assert "cookie-баннера" not in text
    assert "рекламные материалы" not in text
    assert "mixed content" not in text


def test_report_recommendations_are_deduped() -> None:
    report = ReportService().build(
        make_check_result(
            infrastructure=InfrastructureAnalysisResult(
                checked=True,
                external_domains_found=True,
                foreign_services_found=True,
                analytics_services_found=True,
            ),
            external_services=ExternalServicesResult(found=True),
        )
    )

    assert len(report.recommendations) == len(set(report.recommendations))


def test_report_does_not_contain_forbidden_final_phrases() -> None:
    report = ReportService().build(
        make_check_result(
            advertising=AdvertisingAnalysisResult(
                found=True,
                ad_services_found=True,
                erid_found=False,
                ad_marking_found=False,
            ),
            infrastructure=InfrastructureAnalysisResult(
                checked=True,
                external_domains_found=True,
                foreign_services_found=True,
            ),
            accessibility=AccessibilityAnalysisResult(checked=True, issues_found=True),
        )
    )
    text = " ".join(
        [
            *report.summary,
            *report.recommendations,
            *report.manual_review_required,
            *report.limitations,
        ]
    ).lower()

    forbidden = [
        "сайт нарушает закон",
        "сайт незаконен",
        "нарушение 152-фз",
        "нарушение закона о рекламе",
        "данные хранятся за границей",
        "сайт не соответствует гост",
        "реклама оформлена неправильно",
        "согласие отсутствует",
    ]
    for phrase in forbidden:
        assert phrase not in text


def test_report_does_not_include_html_from_check_result() -> None:
    report = ReportService().build(make_check_result())

    assert "<html" not in summary_text(report).lower()
    assert "<html" not in report.recommendation.lower()
