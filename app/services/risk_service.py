import re
from html import unescape
from urllib.parse import urlsplit, urlunsplit

from app.schemas.accessibility import AccessibilityAnalysisResult
from app.schemas.advertising import AdvertisingAnalysisResult
from app.schemas.authentication import AuthenticationResult
from app.schemas.check import CheckMeta
from app.schemas.consents import ConsentsResult
from app.schemas.cookies import CookieAnalysisResult
from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.forms import FormsResult
from app.schemas.infrastructure import InfrastructureAnalysisResult
from app.schemas.policy import PolicyResult
from app.schemas.risk import RiskAssessment, RiskFactor
from app.schemas.security import SecurityResult


class RiskService:
    analytics_types = {"analytics", "tag_manager"}
    link_only_types = {"external_link", "social_network", "messenger"}
    preliminary_cookie_factor_codes = {
        "cookie_banner_not_found",
        "cookies_before_consent_detected",
        "advertising_before_consent_detected",
        "cookie_reject_button_not_found",
        "cookie_reject_did_not_reduce_tracking",
        "advertising_service_without_erid",
        "advertising_service_without_label",
        "possible_ad_blocks_detected",
        "accessibility_medium_issues_detected",
        "accessibility_low_issues_detected",
        "foreign_infrastructure_services_detected",
        "external_infrastructure_services_detected",
        "analytics_infrastructure_detected",
    }
    preliminary_cookie_score_cap = 85

    def assess(
        self,
        forms: FormsResult | None = None,
        consents: ConsentsResult | None = None,
        policy: PolicyResult | None = None,
        external_services: ExternalServicesResult | None = None,
        authentication: AuthenticationResult | None = None,
        security: SecurityResult | None = None,
        cookies: CookieAnalysisResult | None = None,
        advertising: AdvertisingAnalysisResult | None = None,
        accessibility: AccessibilityAnalysisResult | None = None,
        infrastructure: InfrastructureAnalysisResult | None = None,
        check: CheckMeta | str | None = None,
        policy_available: bool | None = None,
    ) -> RiskAssessment:
        factors: list[RiskFactor] = []

        has_personal_data_forms = self._has_personal_data_forms(forms)
        if has_personal_data_forms:
            factors.append(
                self._factor(
                    code="personal_data_collection_detected",
                    level="medium",
                    score=20,
                    message="Обнаружены формы, которые могут собирать персональные данные.",
                    evidence=[field.field_type for form in forms.items for field in form.fields if field.field_type],
                )
            )

        if has_personal_data_forms and not self._policy_found(policy):
            factors.append(
                self._factor(
                    code="privacy_policy_not_found",
                    level="high",
                    score=35,
                    message="При наличии форм сбора данных ссылка на политику не обнаружена.",
                    evidence=["policy.found=false"],
                )
            )

        if self._policy_found(policy) and policy_available is False:
            factors.append(
                self._factor(
                    code="privacy_policy_unavailable",
                    level="medium",
                    score=25,
                    message="Ссылка на политику обнаружена, но документ может быть недоступен.",
                    evidence=[policy.policy_url] if policy and policy.policy_url else [],
                )
            )

        forms_without_consent = self._forms_without_consent(forms, consents)
        if forms_without_consent:
            factors.append(
                self._factor(
                    code="forms_without_consent",
                    level="high",
                    score=35,
                    message="Для части форм не обнаружены признаки согласия на обработку данных.",
                    evidence=forms_without_consent,
                )
            )

        foreign_analytics, foreign_other = self._split_external_services(external_services)
        if foreign_analytics:
            factors.append(
                self._factor(
                    code="foreign_analytics_detected",
                    level="medium",
                    score=25,
                    message="Обнаружены внешние аналитические или tag manager сервисы.",
                    evidence=self._service_evidence(foreign_analytics),
                )
            )

        if foreign_other:
            factors.append(
                self._factor(
                    code="external_resource_detected",
                    level="medium",
                    score=20,
                    message="Обнаружены подключаемые внешние ресурсы, не относящиеся к аналитике.",
                    evidence=self._service_evidence(foreign_other),
                )
            )

        if authentication and authentication.found:
            factors.append(
                self._factor(
                    code="foreign_auth_detected",
                    level="high",
                    score=40,
                    message="Обнаружены признаки авторизации через внешний сервис.",
                    evidence=[
                        provider.url or provider.provider
                        for provider in authentication.providers
                    ],
                )
            )

        if security and security.https_enabled is False:
            factors.append(
                self._factor(
                    code="site_without_https",
                    level="high",
                    score=40,
                    message="Проверенные страницы доступны не только по HTTPS или без HTTPS.",
                    evidence=["https_enabled=false"],
                )
            )

        insecure_personal_forms = self._insecure_personal_forms(forms, security)
        if insecure_personal_forms:
            factors.append(
                self._factor(
                    code="forms_submit_over_http",
                    level="high",
                    score=45,
                    message="Формы с возможным сбором персональных данных отправляются по HTTP.",
                    evidence=insecure_personal_forms,
                )
            )

        cookie_factors = self._cookie_factors(cookies)
        factors.extend(cookie_factors)
        factors.extend(self._advertising_factors(advertising))
        factors.extend(self._accessibility_factors(accessibility))
        factors.extend(self._infrastructure_factors(infrastructure))

        if self._check_status(check) == "partial":
            factors.append(
                self._factor(
                    code="partial_check",
                    level="medium",
                    score=15,
                    message="Проверка выполнена частично, часть признаков могла быть не проверена.",
                    evidence=["status=partial"],
                )
            )

        factors = self._dedupe_factors(factors)
        total_score = self._score_for_factors(factors)
        level = self._level_for_score(total_score)
        level = self._apply_escalation_rules(level, factors, has_personal_data_forms)
        total_score = self._align_score_with_level(total_score, level)

        return RiskAssessment(total_score=total_score, level=level, factors=factors)

    def _has_personal_data_forms(self, forms: FormsResult | None) -> bool:
        if not forms:
            return False

        personal_field_types = {"name", "phone", "email", "address", "message", "company", "inn"}
        return any(
            field.field_type in personal_field_types
            for form in forms.items
            for field in form.fields
        )

    def _policy_found(self, policy: PolicyResult | None) -> bool:
        return bool(policy and policy.found)

    def _forms_without_consent(
        self,
        forms: FormsResult | None,
        consents: ConsentsResult | None,
    ) -> list[str]:
        if not forms or not forms.items:
            return []

        consent_form_ids = {
            consent.form_id
            for consent in (consents.items if consents else [])
            if consent.form_id
        }
        missing: list[str] = []
        for form in forms.items:
            if not form.form_id or form.form_id not in consent_form_ids:
                missing.append(form.form_id or form.page_url)
        return missing

    def _split_external_services(
        self,
        external_services: ExternalServicesResult | None,
    ) -> tuple[list[ExternalServiceItem], list[ExternalServiceItem]]:
        if not external_services:
            return [], []

        analytics: list[ExternalServiceItem] = []
        other: list[ExternalServiceItem] = []
        seen: set[tuple[str | None, str | None, str | None]] = set()

        for item in external_services.items:
            key = (
                item.provider,
                self._normalize_evidence_url(item.url),
                self._normalize_evidence_url(item.page_url),
            )
            if key in seen:
                continue

            seen.add(key)
            if not item.foreign:
                continue
            if item.service_type in self.link_only_types:
                continue

            if item.service_type in self.analytics_types:
                analytics.append(item)
            else:
                other.append(item)

        return analytics, other

    def _service_evidence(self, items: list[ExternalServiceItem]) -> list[str]:
        evidence: list[str] = []
        seen: set[str] = set()
        for item in items:
            value = self._normalize_evidence_url(item.url) or item.provider or item.service_type
            if not value or value in seen:
                continue

            seen.add(value)
            evidence.append(value)

        return evidence

    def _normalize_evidence_url(self, value: str | None) -> str | None:
        if not value:
            return value
        normalized = unescape(value).strip()
        if normalized.startswith("data:image"):
            return "inline data image"
        if "data:image" in normalized:
            prefix = normalized.split("data:image", 1)[0].rstrip()
            if prefix and not prefix.endswith(" "):
                prefix += " "
            return prefix + "inline data image"
        if "<" in normalized and ">" in normalized:
            normalized = re.sub(r"<[^>]{1,200}>", "html element", normalized)
        if len(normalized) > 300:
            normalized = normalized[:300]
        try:
            parts = urlsplit(normalized)
        except ValueError:
            return normalized[:300]
        if parts.scheme and parts.netloc and parts.query:
            return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))[:300]
        return normalized[:300]

    def _insecure_personal_forms(
        self,
        forms: FormsResult | None,
        security: SecurityResult | None,
    ) -> list[str]:
        if not forms or not security or not security.insecure_form_actions:
            return []

        personal_pages = {
            form.page_url
            for form in forms.items
            if any(field.field_type not in {None, "unknown"} for field in form.fields)
        }
        return [
            action.action or action.page_url
            for action in security.insecure_form_actions
            if action.page_url in personal_pages
        ]

    def _cookie_factors(self, cookies: CookieAnalysisResult | None) -> list[RiskFactor]:
        if not cookies or not cookies.analyzed or not cookies.browser_check_available:
            return []

        factors: list[RiskFactor] = []
        if (
            not cookies.banner_found
            and (
                cookies.cookies_before_consent_found
                or cookies.third_party_cookies_before_consent_found
                or cookies.analytics_requests_before_consent_found
                or cookies.advertising_requests_before_consent_found
                or cookies.third_party_requests_before_consent_found
            )
        ):
            factors.append(
                self._factor(
                    code="cookie_banner_not_found",
                    level="medium",
                    score=20,
                    message=(
                        "На момент браузерной проверки cookie-баннер не найден или не был распознан автоматически "
                        "при наличии признаков cookies или аналитических запросов до выбора пользователя."
                    ),
                    evidence=["banner_found=false"],
                )
            )

        if (
            cookies.analytics_requests_before_consent_found
            or cookies.third_party_cookies_before_consent_found
        ):
            factors.append(
                self._factor(
                    code="cookies_before_consent_detected",
                    level="medium",
                    score=20,
                    message=(
                        "Обнаружены признаки cookies или аналитических запросов до явного выбора пользователя."
                    ),
                    evidence=[
                        item.name
                        for item in cookies.cookies_before_consent
                        if item.is_third_party or item.category == "analytics"
                    ],
                )
            )

        if cookies.advertising_requests_before_consent_found:
            factors.append(
                self._factor(
                    code="advertising_before_consent_detected",
                    level="medium",
                    score=25,
                    message="Обнаружены запросы к рекламным сервисам до явного выбора пользователя.",
                    evidence=[
                        item.url
                        for item in cookies.requests_before_consent
                        if item.category == "advertising"
                    ],
                )
            )

        if (
            (cookies.banner_found or cookies.cookies_before_consent_found)
            and not cookies.reject_button_found
        ):
            factors.append(
                self._factor(
                    code="cookie_reject_button_not_found",
                    level="medium",
                    score=20,
                    message="Явная кнопка отклонения cookie не была найдена автоматически; требуется ручная проверка.",
                    evidence=["reject_button_found=false"],
                )
            )

        if cookies.reject_test_performed and (
            cookies.analytics_reduced_after_reject is False
            or cookies.advertising_reduced_after_reject is False
        ):
            factors.append(
                self._factor(
                    code="cookie_reject_did_not_reduce_tracking",
                    level="medium",
                    score=25,
                    message=(
                        "После нажатия кнопки отклонения не зафиксировано заметного снижения запросов "
                        "к сервисам отслеживания; требуется ручная проверка."
                    ),
                    evidence=[
                        "analytics_reduced_after_reject=false"
                        if cookies.analytics_reduced_after_reject is False
                        else "",
                        "advertising_reduced_after_reject=false"
                        if cookies.advertising_reduced_after_reject is False
                        else "",
                    ],
                )
            )

        return factors

    def _advertising_factors(
        self,
        advertising: AdvertisingAnalysisResult | None,
    ) -> list[RiskFactor]:
        if not advertising or not advertising.found:
            return []

        factors: list[RiskFactor] = []
        service_evidence = [service.url for service in advertising.services]
        if advertising.ad_services_found and not advertising.erid_found:
            factors.append(
                self._factor(
                    code="advertising_service_without_erid",
                    level="medium",
                    score=20,
                    message=(
                        "Обнаружены признаки рекламных сервисов без найденного erid на проверенных страницах."
                    ),
                    evidence=service_evidence,
                )
            )

        if advertising.ad_services_found and not advertising.ad_marking_found:
            factors.append(
                self._factor(
                    code="advertising_service_without_label",
                    level="medium",
                    score=15,
                    message=(
                        "Обнаружены признаки рекламных сервисов без найденной явной маркировки рекламы на проверенных страницах."
                    ),
                    evidence=service_evidence,
                )
            )

        if advertising.possible_ad_blocks_found:
            factors.append(
                self._factor(
                    code="possible_ad_blocks_detected",
                    level="low",
                    score=10,
                    message="Обнаружены возможные рекламные блоки по HTML-признакам.",
                    evidence=[
                        item.evidence
                        for item in advertising.text_items
                        if item.item_type == "possible_ad_block"
                    ],
                )
            )

        return factors

    def _infrastructure_factors(
        self,
        infrastructure: InfrastructureAnalysisResult | None,
    ) -> list[RiskFactor]:
        if not infrastructure or not infrastructure.checked or not infrastructure.external_domains_found:
            return []

        factors: list[RiskFactor] = []
        if infrastructure.foreign_services_found:
            factors.append(
                self._factor(
                    code="foreign_infrastructure_services_detected",
                    level="medium",
                    score=20,
                    message="Обнаружены признаки использования иностранных инфраструктурных сервисов.",
                    evidence=self._infrastructure_foreign_evidence(infrastructure),
                )
            )
        else:
            factors.append(
                self._factor(
                    code="external_infrastructure_services_detected",
                    level="low",
                    score=10,
                    message="Обнаружены сторонние инфраструктурные домены.",
                    evidence=[
                        item.domain
                        for item in infrastructure.domains
                        if item.is_third_party
                    ],
                )
            )

        if infrastructure.analytics_services_found:
            factors.append(
                self._factor(
                    code="analytics_infrastructure_detected",
                    level="medium",
                    score=15,
                    message="Обнаружены аналитические инфраструктурные сервисы.",
                    evidence=self._infrastructure_category_evidence(infrastructure, "analytics"),
                )
            )

        return factors

    def _infrastructure_foreign_evidence(
        self,
        infrastructure: InfrastructureAnalysisResult,
    ) -> list[str]:
        service_evidence = [
            f"{item.provider}: {item.domain}"
            for item in infrastructure.services
            if item.likely_foreign is True
        ]
        domain_evidence = [
            item.domain
            for item in infrastructure.domains
            if item.likely_foreign is True and item.is_third_party
        ]
        return service_evidence + domain_evidence

    def _infrastructure_category_evidence(
        self,
        infrastructure: InfrastructureAnalysisResult,
        category: str,
    ) -> list[str]:
        service_evidence = [
            f"{item.provider}: {item.domain}"
            for item in infrastructure.services
            if item.category == category
        ]
        domain_evidence = [
            item.domain
            for item in infrastructure.domains
            if item.category == category and item.is_third_party
        ]
        return service_evidence + domain_evidence

    def _accessibility_factors(
        self,
        accessibility: AccessibilityAnalysisResult | None,
    ) -> list[RiskFactor]:
        if not accessibility or not accessibility.issues_found:
            return []

        medium_issue_found = (
            accessibility.missing_lang
            or accessibility.missing_alt_count > 0
            or accessibility.empty_links_count > 0
            or accessibility.empty_buttons_count > 0
            or accessibility.missing_input_labels_count > 0
            or accessibility.iframe_missing_title_count > 0
        )
        low_issue_found = (
            accessibility.empty_alt_count > 0
            or accessibility.heading_order_warnings_count > 0
            or accessibility.duplicate_ids_count > 0
        )
        medium_issues = [item for item in accessibility.items if item.severity == "medium"]
        low_issues = [item for item in accessibility.items if item.severity == "low"]
        if medium_issue_found:
            return [
                self._factor(
                    code="accessibility_medium_issues_detected",
                    level="medium",
                    score=20,
                    message="Обнаружены признаки возможных проблем доступности на проверенных страницах.",
                    evidence=self._issue_evidence(medium_issues or accessibility.items),
                )
            ]
        if low_issue_found:
            return [
                self._factor(
                    code="accessibility_low_issues_detected",
                    level="low",
                    score=10,
                    message="Обнаружены отдельные технические замечания по доступности.",
                    evidence=self._issue_evidence(low_issues or accessibility.items),
                )
            ]
        return []

    def _issue_evidence(self, items) -> list[str]:
        return [f"{item.issue_type}: {item.evidence}" for item in items]

    def _check_status(self, check: CheckMeta | str | None) -> str | None:
        if isinstance(check, str):
            return check
        if check is None:
            return None
        return check.status

    def _score_for_factors(self, factors: list[RiskFactor]) -> int:
        total_score = min(max(sum(factor.score for factor in factors), 0), 100)
        if self._is_preliminary_cookie_score_dominant(factors):
            return min(total_score, self.preliminary_cookie_score_cap)
        return total_score

    def _is_preliminary_cookie_score_dominant(self, factors: list[RiskFactor]) -> bool:
        if not factors:
            return False

        cookie_score = sum(
            factor.score
            for factor in factors
            if factor.code in self.preliminary_cookie_factor_codes
        )
        if cookie_score == 0:
            return False

        non_cookie_factors = [
            factor
            for factor in factors
            if factor.code not in self.preliminary_cookie_factor_codes
        ]
        if any(factor.level == "high" for factor in non_cookie_factors):
            return False

        non_cookie_score = sum(factor.score for factor in non_cookie_factors)
        return cookie_score >= non_cookie_score

    def _level_for_score(self, score: int) -> str:
        if score <= 30:
            return "low"
        if score <= self.preliminary_cookie_score_cap:
            return "medium"
        return "high"

    def _align_score_with_level(self, score: int, level: str) -> int:
        if level == "low":
            return min(score, 30)
        if level == "medium":
            return min(score, self.preliminary_cookie_score_cap)
        return max(score, self.preliminary_cookie_score_cap + 1)

    def _apply_escalation_rules(
        self,
        level: str,
        factors: list[RiskFactor],
        has_personal_data_forms: bool,
    ) -> str:
        factor_codes = {factor.code for factor in factors}
        high_conditions = (
            {
                "personal_data_collection_detected",
                "privacy_policy_not_found",
                "forms_without_consent",
            }.issubset(factor_codes),
            {"personal_data_collection_detected", "forms_submit_over_http"}.issubset(factor_codes),
            "foreign_auth_detected" in factor_codes,
        )
        if any(high_conditions):
            return "high"
        if (
            level == "high"
            and not has_personal_data_forms
            and "foreign_auth_detected" not in factor_codes
        ):
            return "medium"
        return level

    def _factor(
        self,
        code: str,
        level: str,
        score: int,
        message: str,
        evidence: list[str],
    ) -> RiskFactor:
        return RiskFactor(
            code=code,
            level=level,
            score=score,
            message=message,
            evidence=self._dedupe_evidence(evidence),
        )

    def _dedupe_evidence(self, evidence: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in evidence:
            normalized = self._normalize_evidence_url(item)
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            deduped.append(normalized)
            if len(deduped) >= 5:
                break

        return deduped

    def _dedupe_factors(self, factors: list[RiskFactor]) -> list[RiskFactor]:
        deduped: list[RiskFactor] = []
        seen: set[str] = set()
        for factor in factors:
            if factor.code in seen:
                continue
            seen.add(factor.code)
            deduped.append(factor)
        return deduped
