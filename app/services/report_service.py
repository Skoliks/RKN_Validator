from app.schemas.check import CheckResult
from app.schemas.report import ReportResult


class ReportService:
    failed_default_message = "Проверку выполнить не удалось."

    def build(self, check_result: CheckResult) -> ReportResult:
        if check_result.check.status == "failed":
            return ReportResult(
                summary=self._failed_summary(check_result),
                recommendation="Рекомендуется проверить корректность адреса и доступность сайта, затем повторить проверку.",
                llm_generated=False,
            )

        summary = self._build_summary(check_result)
        recommendation = self._build_recommendation(check_result)
        return ReportResult(
            summary=summary,
            recommendation=recommendation,
            llm_generated=False,
        )

    def _failed_summary(self, check_result: CheckResult) -> str:
        if check_result.availability and check_result.availability.message:
            reason = check_result.availability.message
        else:
            reason = self.failed_default_message

        return f"{reason} Проверка завершилась со статусом failed. Рекомендуется ручная проверка исходных данных."

    def _build_summary(self, check_result: CheckResult) -> str:
        sentences: list[str] = []
        risk = check_result.risk_assessment

        if check_result.check.status == "partial":
            sentences.append("Проверка выполнена частично, поэтому часть признаков могла быть не проверена.")

        if check_result.availability and check_result.availability.available:
            sentences.append("Сайт был доступен на момент технической проверки.")

        if check_result.pages:
            sentences.append(
                f"На проверенных страницах обработано {check_result.pages.total_checked} страниц из {check_result.pages.total_found} найденных."
            )

        if check_result.forms and check_result.forms.found:
            sentences.append("Обнаружены признаки форм, которые могут собирать данные пользователей.")
        elif check_result.forms is not None:
            sentences.append("На проверенных страницах формы сбора данных не найдены.")

        if check_result.policy and check_result.policy.found:
            sentences.append("На проверенных страницах найдена ссылка на политику, связанную с обработкой данных.")
        elif check_result.policy is not None:
            sentences.append("На проверенных страницах не найдено ссылки на политику обработки данных.")

        if risk:
            sentences.append(
                f"Техническая оценка показывает уровень потенциального риска {risk.level} при сумме {risk.total_score} из 100."
            )
            if risk.factors:
                factor_names = ", ".join(factor.code for factor in risk.factors[:3])
                sentences.append(f"Основные обнаруженные признаки: {factor_names}.")

        if check_result.external_services and check_result.external_services.found:
            sentences.append("Также обнаружены признаки использования сторонних сервисов.")

        if not sentences:
            sentences.append("По переданным результатам проверки значимые признаки не обнаружены.")

        sentences.append("Рекомендуется ручная проверка для подтверждения выводов.")
        return " ".join(sentences[:6])

    def _build_recommendation(self, check_result: CheckResult) -> str:
        risk = check_result.risk_assessment
        level = risk.level if risk else "low"
        factor_codes = {factor.code for factor in risk.factors} if risk else set()

        if level == "high":
            return (
                "Рекомендуется провести ручную проверку и доработать документы, формы и сторонние сервисы по найденным признакам. "
                "Особое внимание стоит уделить передаче данных через формы и внешним провайдерам."
            )

        if level == "medium":
            if "foreign_analytics_detected" in factor_codes or "foreign_service_detected" in factor_codes:
                return "Рекомендуется вручную проверить замечания по сторонним сервисам и документам сайта."
            return "Рекомендуется вручную проверить найденные замечания и при необходимости уточнить документы сайта."

        return "Рекомендуется периодически повторять проверку и отслеживать изменения форм, документов и сторонних сервисов."
