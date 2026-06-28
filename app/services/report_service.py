from app.schemas.check import CheckResult
from app.schemas.report import ReportResult
from app.schemas.risk import RiskFactor


class ReportService:
    failed_default_message = "Проверку выполнить не удалось."
    level_labels = {
        "low": "низкий",
        "medium": "средний",
        "high": "высокий",
    }
    factor_labels = {
        "personal_data_collection_detected": "обнаружены формы, которые могут собирать персональные данные",
        "privacy_policy_not_found": "не найдена политика обработки персональных данных",
        "privacy_policy_unavailable": "ссылка на политику найдена, но документ недоступен",
        "forms_without_consent": "для части форм не найдены признаки согласия на обработку данных",
        "foreign_analytics_detected": "найдены иностранные аналитические сервисы",
        "external_resource_detected": "найдены подключаемые внешние ресурсы, требующие ручной проверки",
        "foreign_auth_detected": "найдены признаки авторизации через внешний сервис",
        "site_without_https": "часть страниц доступна без HTTPS",
        "forms_submit_over_http": "форма с возможным сбором данных отправляется по HTTP",
        "partial_check": "проверка выполнена частично",
    }

    def build(self, check_result: CheckResult) -> ReportResult:
        if check_result.check.status == "failed":
            return ReportResult(
                summary=self._failed_summary(check_result),
                recommendation=(
                    "Рекомендуется проверить корректность адреса и доступность сайта, "
                    "затем повторить проверку."
                ),
                llm_generated=False,
            )

        return ReportResult(
            summary=self._build_summary(check_result),
            recommendation=self._build_recommendation(check_result),
            llm_generated=False,
        )

    def _failed_summary(self, check_result: CheckResult) -> str:
        reason = (
            check_result.availability.message
            if check_result.availability and check_result.availability.message
            else self.failed_default_message
        )
        return (
            f"{reason} Проверка завершилась со статусом failed. "
            "Рекомендуется ручная проверка исходных данных."
        )

    def _build_summary(self, check_result: CheckResult) -> str:
        sentences: list[str] = []
        risk = check_result.risk_assessment

        if check_result.check.status == "partial":
            sentences.append(
                "Проверка выполнена частично, поэтому часть признаков могла быть не проверена."
            )

        if check_result.availability and check_result.availability.available:
            sentences.append("Сайт был доступен на момент технической проверки.")

        if check_result.pages:
            page_word = self._page_word(check_result.pages.total_checked)
            sentences.append(
                f"Проверено {check_result.pages.total_checked} {page_word} "
                f"из {check_result.pages.total_found} найденных."
            )

        if check_result.forms and check_result.forms.found:
            sentences.append(
                "Обнаружены формы, которые могут собирать данные пользователей."
            )
        elif check_result.forms is not None:
            sentences.append("На проверенных страницах формы сбора данных не найдены.")

        if check_result.policy and check_result.policy.found:
            sentences.append(
                "Найдена ссылка на документ, связанный с конфиденциальностью и обработкой персональной информации."
            )
        elif check_result.policy and check_result.policy.candidates:
            sentences.append(
                "Найдены страницы, похожие на документ политики обработки персональных данных; "
                "нужна ручная проверка содержания."
            )
        elif check_result.policy is not None:
            sentences.append(
                "На проверенных страницах ссылка на политику обработки персональных данных не найдена."
            )

        if risk:
            level = self._level_label(risk.level)
            sentences.append(
                f"Техническая оценка показывает {level} уровень потенциального риска "
                f"при сумме {risk.total_score} из 100."
            )
            factor_text = self._factor_text(risk.factors)
            if factor_text:
                sentences.append(f"Основные признаки: {factor_text}.")

        if self._has_only_external_services_without_forms(check_result):
            sentences.append(
                "Риск низкий, но найденные сторонние сервисы рекомендуется проверить вручную."
            )
        elif check_result.external_services and check_result.external_services.found:
            sentences.append("Также обнаружены признаки использования сторонних сервисов.")

        if not sentences:
            sentences.append(
                "По переданным результатам проверки значимые признаки не обнаружены."
            )

        sentences.append("Рекомендуется ручная проверка для подтверждения выводов.")
        return " ".join(sentences[:7])

    def _build_recommendation(self, check_result: CheckResult) -> str:
        risk = check_result.risk_assessment
        level = risk.level if risk else "low"
        factor_codes = {factor.code for factor in risk.factors} if risk else set()

        if self._has_only_external_services_without_forms(check_result):
            return (
                "Общий риск низкий. Рекомендуется вручную проверить назначение "
                "сторонних сервисов и условия передачи данных."
            )

        if level == "high":
            return (
                "Рекомендуется провести ручную проверку и доработать документы, формы "
                "и сторонние сервисы по найденным признакам. Особое внимание стоит "
                "уделить передаче данных через формы и внешним провайдерам."
            )

        if level == "medium":
            if "foreign_analytics_detected" in factor_codes or "external_resource_detected" in factor_codes:
                return (
                    "Рекомендуется вручную проверить замечания по сторонним сервисам "
                    "и документам сайта."
                )
            return (
                "Рекомендуется вручную проверить найденные замечания и при необходимости "
                "уточнить документы сайта."
            )

        return (
            "Рекомендуется периодически повторять проверку и отслеживать изменения форм, "
            "документов и сторонних сервисов."
        )

    def _level_label(self, level: str) -> str:
        return self.level_labels.get(level, level)

    def _factor_text(self, factors: list[RiskFactor]) -> str:
        labels: list[str] = []
        seen: set[str] = set()
        for factor in factors[:3]:
            label = factor.message or self.factor_labels.get(factor.code, factor.code)
            label = label.strip().rstrip(".")
            if not label or label in seen:
                continue

            seen.add(label)
            labels.append(label)

        return "; ".join(labels)

    def _has_only_external_services_without_forms(self, check_result: CheckResult) -> bool:
        has_forms = bool(check_result.forms and check_result.forms.found)
        has_external = bool(check_result.external_services and check_result.external_services.found)
        has_auth = bool(check_result.authentication and check_result.authentication.found)
        risk_level = check_result.risk_assessment.level if check_result.risk_assessment else "low"
        return has_external and not has_forms and not has_auth and risk_level == "low"

    def _page_word(self, count: int) -> str:
        if count % 10 == 1 and count % 100 != 11:
            return "страница"
        if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
            return "страницы"
        return "страниц"
