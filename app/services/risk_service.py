from html import unescape

from app.schemas.authentication import AuthenticationResult
from app.schemas.check import CheckMeta
from app.schemas.consents import ConsentsResult
from app.schemas.cookies import CookieAnalysisResult
from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.forms import FormsResult
from app.schemas.policy import PolicyResult
from app.schemas.risk import RiskAssessment, RiskFactor
from app.schemas.security import SecurityResult


class RiskService:
    analytics_types = {"analytics", "tag_manager"}
    link_only_types = {"social_network", "messenger"}
    preliminary_cookie_factor_codes = {
        "cookie_banner_not_found",
        "cookies_before_consent_detected",
        "advertising_before_consent_detected",
        "cookie_reject_button_not_found",
        "cookie_reject_did_not_reduce_tracking",
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
        return unescape(value).strip()

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
                or cookies.analytics_requests_before_consent_found
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

    def _check_status(self, check: CheckMeta | str | None) -> str | None:
        if isinstance(check, str):
            return check
        if check is None:
            return None
        return check.status

    def _score_for_factors(self, factors: list[RiskFactor]) -> int:
        total_score = min(sum(factor.score for factor in factors), 100)
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
            if not item or item in seen:
                continue

            seen.add(item)
            deduped.append(item)
            if len(deduped) >= 5:
                break

        return deduped
