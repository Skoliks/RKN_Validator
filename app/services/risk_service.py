from app.schemas.authentication import AuthenticationResult
from app.schemas.check import CheckMeta
from app.schemas.consents import ConsentsResult
from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.forms import FormsResult
from app.schemas.policy import PolicyResult
from app.schemas.risk import RiskAssessment, RiskFactor
from app.schemas.security import SecurityResult


class RiskService:
    analytics_types = {"analytics", "tag_manager"}

    def assess(
        self,
        forms: FormsResult | None = None,
        consents: ConsentsResult | None = None,
        policy: PolicyResult | None = None,
        external_services: ExternalServicesResult | None = None,
        authentication: AuthenticationResult | None = None,
        security: SecurityResult | None = None,
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
                    code="foreign_service_detected",
                    level="medium",
                    score=20,
                    message="Обнаружены внешние сервисы, не относящиеся к аналитике.",
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

        total_score = min(sum(factor.score for factor in factors), 100)
        level = self._level_for_score(total_score)
        level = self._apply_escalation_rules(level, factors)

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
            key = (item.provider, item.url, item.page_url)
            if key in seen:
                continue

            seen.add(key)
            if item.service_type in self.analytics_types:
                analytics.append(item)
            else:
                other.append(item)

        return analytics, other

    def _service_evidence(self, items: list[ExternalServiceItem]) -> list[str]:
        return [item.url or item.provider or item.service_type for item in items]

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

    def _check_status(self, check: CheckMeta | str | None) -> str | None:
        if isinstance(check, str):
            return check
        if check is None:
            return None
        return check.status

    def _level_for_score(self, score: int) -> str:
        if score <= 30:
            return "low"
        if score <= 70:
            return "medium"
        return "high"

    def _apply_escalation_rules(self, level: str, factors: list[RiskFactor]) -> str:
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
            evidence=[item for item in evidence if item],
        )
