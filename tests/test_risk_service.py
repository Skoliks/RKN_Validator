from datetime import UTC, datetime

from app.schemas.accessibility import AccessibilityAnalysisResult, AccessibilityIssueItem
from app.schemas.advertising import AdvertisingAnalysisResult, AdvertisingServiceItem
from app.schemas.authentication import AuthenticationResult, AuthProviderItem
from app.schemas.check import CheckMeta
from app.schemas.consents import ConsentItem, ConsentsResult
from app.schemas.cookies import CookieAnalysisResult, CookieBeforeConsentItem, CookieNetworkRequestItem
from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.forms import FormField, FormItem, FormsResult
from app.schemas.infrastructure import InfrastructureAnalysisResult, InfrastructureDomainItem
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


def assert_score_level_consistent(assessment) -> None:
    if assessment.level == "low":
        assert assessment.total_score <= 30
    elif assessment.level == "medium":
        assert 31 <= assessment.total_score <= 85
    else:
        assert assessment.total_score >= 86


def make_cookie_only_risk() -> CookieAnalysisResult:
    return CookieAnalysisResult(
        browser_check_available=True,
        analyzed=True,
        banner_found=False,
        cookies_before_consent_found=True,
        third_party_cookies_before_consent_found=True,
        analytics_requests_before_consent_found=True,
        advertising_requests_before_consent_found=True,
        reject_button_found=False,
        reject_test_performed=True,
        analytics_reduced_after_reject=False,
        advertising_reduced_after_reject=False,
        cookies_before_consent=[
            CookieBeforeConsentItem(
                name="_ga",
                domain=".google-analytics.com",
                is_third_party=True,
                category="analytics",
            )
        ],
        requests_before_consent=[
            CookieNetworkRequestItem(
                url="https://doubleclick.net/activity",
                domain="doubleclick.net",
                category="advertising",
                is_third_party=True,
            )
        ],
    )


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
    assert_score_level_consistent(result)


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
    assert_score_level_consistent(result)


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
    assert "external_resource_detected" not in factor_codes(result)


def test_yandex_metrika_does_not_add_foreign_analytics_factor() -> None:
    result = RiskService().assess(
        forms=FormsResult(),
        external_services=ExternalServicesResult(
            found=True,
            items=[
                ExternalServiceItem(
                    service_type="analytics",
                    provider="Yandex Metrika",
                    url="https://mc.yandex.ru/watch/12345",
                    page_url="https://example.ru",
                    foreign=False,
                )
            ],
        ),
        security=SecurityResult(https_enabled=True),
        check=make_check(),
    )

    assert result.level == "low"
    assert result.total_score == 0
    assert "foreign_analytics_detected" not in factor_codes(result)


def test_social_network_links_without_forms_do_not_escalate_to_high() -> None:
    result = RiskService().assess(
        forms=FormsResult(),
        external_services=ExternalServicesResult(
            found=True,
            items=[
                ExternalServiceItem(
                    service_type="social_network",
                    provider="Facebook",
                    url="https://facebook.com/company",
                    page_url="https://example.ru",
                ),
                ExternalServiceItem(
                    service_type="social_network",
                    provider="Instagram",
                    url="https://instagram.com/company",
                    page_url="https://example.ru",
                ),
            ],
        ),
        authentication=AuthenticationResult(),
        security=SecurityResult(https_enabled=True),
        check=make_check(),
    )

    assert result.level != "high"
    assert "foreign_auth_detected" not in factor_codes(result)
    assert "external_resource_detected" not in factor_codes(result)


def test_facebook_company_link_is_not_external_resource_factor() -> None:
    result = RiskService().assess(
        forms=FormsResult(),
        external_services=ExternalServicesResult(
            found=True,
            items=[
                ExternalServiceItem(
                    service_type="social_network",
                    provider="Facebook",
                    url="https://facebook.com/company",
                    page_url="https://example.ru",
                )
            ],
        ),
        authentication=AuthenticationResult(),
        security=SecurityResult(https_enabled=True),
        check=make_check(),
    )

    assert "external_resource_detected" not in factor_codes(result)


def test_service_evidence_does_not_contain_duplicates_after_html_unescape() -> None:
    result = RiskService().assess(
        external_services=ExternalServicesResult(
            found=True,
            items=[
                ExternalServiceItem(
                    service_type="external_link",
                    provider="Partner",
                    url="https://partner.example.com/widget?a=1&amp;b=2",
                    page_url="https://example.ru",
                ),
                ExternalServiceItem(
                    service_type="external_link",
                    provider="Partner",
                    url="https://partner.example.com/widget?a=1&b=2",
                    page_url="https://example.ru",
                ),
            ],
        ),
        security=SecurityResult(https_enabled=True),
        check=make_check(),
    )

    factor = next(factor for factor in result.factors if factor.code == "external_resource_detected")
    assert factor.evidence == ["https://partner.example.com/widget"]


def test_risk_assessment_consistency_limits_score_evidence_and_factor_codes() -> None:
    result = RiskService().assess(
        cookies=CookieAnalysisResult(
            browser_check_available=True,
            analyzed=True,
            banner_found=False,
            cookies_before_consent_found=True,
            third_party_cookies_before_consent_found=True,
            analytics_requests_before_consent_found=True,
            advertising_requests_before_consent_found=True,
            requests_before_consent=[
                CookieNetworkRequestItem(
                    url=f"https://doubleclick.net/activity?id={index}&payload=long",
                    domain="doubleclick.net",
                    category="advertising",
                    is_third_party=True,
                )
                for index in range(10)
            ],
        ),
        advertising=AdvertisingAnalysisResult(
            found=True,
            ad_services_found=True,
            erid_found=False,
            ad_marking_found=False,
            services=[
                AdvertisingServiceItem(
                    service_type="advertising",
                    provider="Google DoubleClick",
                    url=f"https://googleads.g.doubleclick.net/pagead/id?slot={index}",
                    domain="googleads.g.doubleclick.net",
                    source="browser_network",
                )
                for index in range(10)
            ],
        ),
        infrastructure=InfrastructureAnalysisResult(
            checked=True,
            external_domains_found=True,
            foreign_services_found=True,
            domains=[
                InfrastructureDomainItem(
                    domain=f"cdn{index}.example.com",
                    category="cdn",
                    is_third_party=True,
                    likely_foreign=True,
                    source="browser_network",
                )
                for index in range(10)
            ],
        ),
        check=make_check(),
    )

    assert result.total_score <= 100
    assert result.level not in {"high", "critical"}
    codes = [factor.code for factor in result.factors]
    assert len(codes) == len(set(codes))
    for factor in result.factors:
        assert len(factor.evidence) <= 5
        assert all("?" not in item for item in factor.evidence)


def test_risk_evidence_does_not_include_large_data_images() -> None:
    result = RiskService().assess(
        accessibility=AccessibilityAnalysisResult(
            checked=True,
            issues_found=True,
            missing_alt_count=1,
            items=[
                AccessibilityIssueItem(
                    issue_type="missing_image_alt",
                    page_url="https://example.ru",
                    element="img",
                    evidence="data:image/png;base64," + ("a" * 500),
                    severity="medium",
                )
            ],
        ),
        check=make_check(),
    )

    factor = next(
        factor
        for factor in result.factors
        if factor.code == "accessibility_medium_issues_detected"
    )

    assert factor.evidence == ["missing_image_alt: inline data image"]


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
    assert_score_level_consistent(result)


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


def test_cookie_banner_not_found_added_only_with_browser_evidence() -> None:
    result = RiskService().assess(
        cookies=CookieAnalysisResult(
            browser_check_available=True,
            analyzed=True,
            banner_found=False,
            cookies_before_consent_found=True,
            analytics_requests_before_consent_found=True,
        ),
        check=make_check(),
    )

    assert "cookie_banner_not_found" in factor_codes(result)
    assert result.level == "medium"
    assert_score_level_consistent(result)


def test_cookie_factors_not_added_when_browser_check_unavailable() -> None:
    result = RiskService().assess(
        cookies=CookieAnalysisResult(
            browser_check_available=False,
            analyzed=False,
            cookies_before_consent_found=True,
            analytics_requests_before_consent_found=True,
        ),
        check=make_check(),
    )

    assert {
        "cookie_banner_not_found",
        "cookies_before_consent_detected",
        "advertising_before_consent_detected",
    }.isdisjoint(factor_codes(result))


def test_cookie_risk_factors_for_third_party_and_advertising() -> None:
    result = RiskService().assess(
        cookies=CookieAnalysisResult(
            browser_check_available=True,
            analyzed=True,
            banner_found=True,
            third_party_cookies_before_consent_found=True,
            advertising_requests_before_consent_found=True,
            cookies_before_consent=[
                CookieBeforeConsentItem(
                    name="ad",
                    domain="doubleclick.net",
                    is_third_party=True,
                    category="advertising",
                )
            ],
            requests_before_consent=[
                CookieNetworkRequestItem(
                    url="https://doubleclick.net/activity",
                    domain="doubleclick.net",
                    category="advertising",
                    is_third_party=True,
                )
            ],
        ),
        check=make_check(),
    )

    assert "cookies_before_consent_detected" in factor_codes(result)
    assert "advertising_before_consent_detected" in factor_codes(result)
    assert result.level == "medium"
    assert_score_level_consistent(result)


def test_cookie_browser_only_risk_is_capped_at_medium_score() -> None:
    result = RiskService().assess(cookies=make_cookie_only_risk(), check=make_check())

    assert result.total_score <= 85
    assert result.total_score == 85
    assert result.level == "medium"
    assert {
        "cookie_banner_not_found",
        "cookies_before_consent_detected",
        "advertising_before_consent_detected",
        "cookie_reject_button_not_found",
        "cookie_reject_did_not_reduce_tracking",
    }.issubset(factor_codes(result))
    assert_score_level_consistent(result)


def test_cookie_browser_cap_does_not_hide_non_cookie_high_risk() -> None:
    result = RiskService().assess(
        cookies=make_cookie_only_risk(),
        authentication=AuthenticationResult(
            found=True,
            providers=[AuthProviderItem(provider="Google", page_url="https://example.ru")],
        ),
        check=make_check(),
    )

    assert result.total_score > 85
    assert result.level == "high"
    assert "foreign_auth_detected" in factor_codes(result)
    assert_score_level_consistent(result)


def test_cookie_advertising_evidence_is_deduplicated_and_limited() -> None:
    duplicated_requests = [
        CookieNetworkRequestItem(
            url="https://doubleclick.net/activity",
            domain="doubleclick.net",
            category="advertising",
            is_third_party=True,
        ),
        CookieNetworkRequestItem(
            url="https://doubleclick.net/activity",
            domain="doubleclick.net",
            category="advertising",
            is_third_party=True,
        ),
        *[
            CookieNetworkRequestItem(
                url=f"https://doubleclick.net/activity/{index}",
                domain="doubleclick.net",
                category="advertising",
                is_third_party=True,
            )
            for index in range(10)
        ],
    ]

    result = RiskService().assess(
        cookies=CookieAnalysisResult(
            browser_check_available=True,
            analyzed=True,
            banner_found=True,
            advertising_requests_before_consent_found=True,
            requests_before_consent=duplicated_requests,
        ),
        check=make_check(),
    )

    factor = next(
        factor
        for factor in result.factors
        if factor.code == "advertising_before_consent_detected"
    )
    assert factor.evidence == [
        "https://doubleclick.net/activity",
        "https://doubleclick.net/activity/0",
        "https://doubleclick.net/activity/1",
        "https://doubleclick.net/activity/2",
        "https://doubleclick.net/activity/3",
    ]
