from datetime import UTC, datetime

from app.schemas.authentication import AuthenticationResult, AuthProviderItem
from app.schemas.check import CheckMeta
from app.schemas.consents import ConsentItem, ConsentsResult
from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.forms import FormField, FormItem, FormsResult
from app.schemas.policy import PolicyMatchedLink, PolicyResult
from app.schemas.security import InsecureFormAction, SecurityResult
from app.services.risk_service import RiskService


def make_check(status: str = "completed") -> CheckMeta:
    return CheckMeta(
        status=status,
        checked_at=datetime.now(UTC),
        duration_ms=100,
        mode="sync",
        interface="api",
    )


def make_personal_forms() -> FormsResult:
    return FormsResult(
        found=True,
        total=1,
        items=[
            FormItem(
                form_id="contact",
                page_url="https://example.ru",
                action="/send",
                method="post",
                fields=[FormField(name="phone", field_type="phone")],
            )
        ],
    )


def make_consents() -> ConsentsResult:
    return ConsentsResult(
        found=True,
        items=[
            ConsentItem(
                page_url="https://example.ru",
                form_id="contact",
                consent_type="personal_data",
                text="Согласие на обработку персональных данных",
            )
        ],
    )


def make_policy() -> PolicyResult:
    return PolicyResult(
        found=True,
        policy_url="https://example.ru/privacy",
        matched_links=[
            PolicyMatchedLink(
                page_url="https://example.ru",
                href="https://example.ru/privacy",
                text="Политика конфиденциальности",
            )
        ],
    )


def factor_codes(assessment) -> set[str]:
    return {factor.code for factor in assessment.factors}


def test_good_site_has_low_risk() -> None:
    result = RiskService().assess(
        forms=FormsResult(),
        consents=ConsentsResult(),
        policy=make_policy(),
        external_services=ExternalServicesResult(),
        authentication=AuthenticationResult(),
        security=SecurityResult(https_enabled=True),
        check=make_check(),
    )

    assert result.total_score == 0
    assert result.level == "low"
    assert result.factors == []


def test_forms_without_policy_and_consent_escalates_to_high() -> None:
    result = RiskService().assess(
        forms=make_personal_forms(),
        consents=ConsentsResult(),
        policy=PolicyResult(found=False),
        security=SecurityResult(https_enabled=True),
        check=make_check(),
    )

    assert result.level == "high"
    assert result.total_score == 90
    assert {
        "personal_data_collection_detected",
        "privacy_policy_not_found",
        "forms_without_consent",
    }.issubset(factor_codes(result))


def test_google_analytics_with_documents_is_medium_without_duplicate_service_factor() -> None:
    result = RiskService().assess(
        forms=make_personal_forms(),
        consents=make_consents(),
        policy=make_policy(),
        external_services=ExternalServicesResult(
            found=True,
            items=[
                ExternalServiceItem(
                    service_type="analytics",
                    provider="Google Analytics",
                    url="https://www.google-analytics.com/analytics.js",
                    page_url="https://example.ru",
                )
            ],
        ),
        security=SecurityResult(https_enabled=True),
        check=make_check(),
    )

    assert result.level == "medium"
    assert "foreign_analytics_detected" in factor_codes(result)
    assert "foreign_service_detected" not in factor_codes(result)


def test_foreign_auth_escalates_to_high() -> None:
    result = RiskService().assess(
        forms=FormsResult(),
        policy=make_policy(),
        authentication=AuthenticationResult(
            found=True,
            providers=[
                AuthProviderItem(
                    provider="Google",
                    page_url="https://example.ru",
                    url="https://accounts.google.com/oauth",
                )
            ],
        ),
        security=SecurityResult(https_enabled=True),
        check=make_check(),
    )

    assert result.level == "high"
    assert "foreign_auth_detected" in factor_codes(result)


def test_forms_submit_over_http_escalates_to_high_and_score_is_capped() -> None:
    result = RiskService().assess(
        forms=make_personal_forms(),
        consents=ConsentsResult(),
        policy=PolicyResult(found=False),
        external_services=ExternalServicesResult(
            found=True,
            items=[
                ExternalServiceItem(
                    service_type="external_link",
                    provider="Partner",
                    url="https://partner.example.com",
                    page_url="https://example.ru",
                )
            ],
        ),
        authentication=AuthenticationResult(
            found=True,
            providers=[AuthProviderItem(provider="Google", page_url="https://example.ru")],
        ),
        security=SecurityResult(
            https_enabled=False,
            insecure_form_actions=[
                InsecureFormAction(
                    page_url="https://example.ru",
                    action="http://example.ru/send",
                    reason="Form action uses insecure HTTP.",
                )
            ],
        ),
        check=make_check("partial"),
    )

    assert result.level == "high"
    assert result.total_score == 100
    assert "forms_submit_over_http" in factor_codes(result)


def test_partial_check_adds_partial_factor() -> None:
    result = RiskService().assess(
        forms=FormsResult(),
        policy=make_policy(),
        security=SecurityResult(https_enabled=True),
        check=make_check("partial"),
    )

    assert result.total_score == 15
    assert result.level == "low"
    assert "partial_check" in factor_codes(result)
