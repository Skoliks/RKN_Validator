from app.schemas.check import CheckResult
from app.schemas.report import ReportResult
from app.schemas.risk import RiskFactor


class ReportService:
    summary_item_limit = 12
    failed_default_message = "Проверку выполнить не удалось."
    level_labels = {
        "low": "низкий",
        "medium": "средний",
        "high": "высокий",
        "critical": "критический",
    }

    def build(self, check_result: CheckResult) -> ReportResult:
        if check_result.check.status == "failed":
            summary = self._failed_summary(check_result)
            recommendations = [
                "Проверить корректность адреса и доступность сайта, затем повторить проверку."
            ]
            limitations = self._build_limitations(check_result)
            return ReportResult(
                summary=summary,
                recommendations=recommendations,
                recommendation=" ".join(recommendations),
                checked_areas=self._build_checked_areas(check_result),
                manual_review_required=[
                    "Исходные данные и доступность сайта требуют ручной проверки."
                ],
                limitations=limitations,
                llm_generated=False,
            )

        recommendations = self._build_recommendations(check_result)
        return ReportResult(
            summary=self._build_summary(check_result),
            recommendations=recommendations,
            recommendation=" ".join(recommendations),
            checked_areas=self._build_checked_areas(check_result),
            manual_review_required=self._build_manual_review_required(check_result),
            limitations=self._build_limitations(check_result),
            llm_generated=False,
        )

    def _failed_summary(self, check_result: CheckResult) -> list[str]:
        reason = (
            check_result.availability.message
            if check_result.availability and check_result.availability.message
            else self.failed_default_message
        )
        return self._dedupe_text(
            [
                reason,
                "Проверка завершилась со статусом failed.",
                "Рекомендуется ручная проверка исходных данных.",
            ]
        )

    def _build_summary(self, check_result: CheckResult) -> list[str]:
        items: list[str] = []
        risk = check_result.risk_assessment

        if check_result.check.status == "partial":
            items.append(
                "Проверка выполнена частично, поэтому часть признаков могла быть не проверена."
            )
        elif check_result.availability and check_result.availability.available:
            items.append("Сайт был доступен на момент технической проверки.")

        if check_result.pages:
            page_word = self._page_word(check_result.pages.total_checked)
            items.append(
                f"Проверено {check_result.pages.total_checked} {page_word} из {check_result.pages.total_found} найденных."
            )

        if risk:
            level = self.level_labels.get(risk.level, risk.level)
            items.append(
                f"Техническая оценка показывает {level} уровень потенциального риска при сумме {risk.total_score} из 100."
            )

        cookies = check_result.cookies
        if cookies and cookies.analyzed:
            cookie_evidence_found = self._cookie_evidence_found(cookies)
            if cookies.cookies_before_consent_found:
                items.append(
                    "На момент браузерной проверки обнаружены cookies после первичной загрузки страницы до явного выбора пользователя."
                )
            if not cookies.banner_found and cookie_evidence_found:
                items.append(
                    "Cookie-баннер не был найден или не был распознан автоматически; требуется ручная проверка."
                )
            if (
                (cookies.banner_found or cookie_evidence_found)
                and cookies.interaction_available
                and not cookies.reject_button_found
            ):
                items.append(
                    "Явная кнопка отклонения cookie не была найдена автоматически; требуется ручная проверка."
                )
            if cookies.reject_test_performed and (
                cookies.analytics_reduced_after_reject is False
                or cookies.advertising_reduced_after_reject is False
            ):
                items.append(
                    "После нажатия кнопки отклонения не зафиксировано заметного снижения cookies или запросов к сервисам отслеживания; требуется ручная проверка."
                )

        advertising = check_result.advertising
        if advertising:
            if advertising.ad_services_found:
                items.append("Обнаружены признаки подключения рекламных сервисов.")
                if not advertising.erid_found:
                    items.append(
                        "На проверенных страницах не найден erid; требуется ручная проверка рекламных материалов."
                    )
                if not advertising.ad_marking_found:
                    items.append("Явная маркировка рекламы не была найдена автоматически.")
            elif not advertising.found:
                items.append("Явные рекламные признаки на проверенных страницах не найдены.")

        infrastructure = check_result.infrastructure
        if infrastructure:
            if infrastructure.external_domains_found:
                items.append("Обнаружены сторонние домены и внешние инфраструктурные сервисы.")
                if infrastructure.foreign_services_found:
                    items.append(
                        "Обнаружены признаки использования иностранных сервисов; требуется ручная проверка условий передачи и обработки данных."
                    )
            elif infrastructure.checked:
                items.append(
                    "Явные сторонние инфраструктурные домены на проверенных страницах не найдены."
                )

        accessibility = check_result.accessibility
        if accessibility:
            if accessibility.issues_found:
                items.append(
                    "Обнаружены признаки возможных технических проблем доступности; требуется ручная проверка."
                )
            else:
                items.append(
                    "Явные технические замечания по доступности на проверенных страницах не найдены."
                )

        if check_result.security and check_result.security.has_mixed_content:
            items.append(
                "Обнаружены признаки смешанного содержимого: часть ресурсов запрашивается по небезопасному HTTP."
            )

        owner = check_result.owner_requisites
        if owner:
            if owner.found:
                items.append("На проверенных страницах обнаружены реквизиты владельца сайта.")
            if not owner.privacy_email_found:
                items.append(
                    "Отдельный e-mail для обращений по персональным данным не найден автоматически."
                )

        domain = check_result.domain_compliance
        if domain and domain.status == "not_applicable":
            items.append(
                "Требование идентификации администратора через ЕСИА к данной доменной зоне не применяется."
            )

        if not items:
            items.append(
                "По переданным результатам проверки значимые признаки не обнаружены."
            )

        return self._dedupe_text(items)[: self.summary_item_limit]

    def _build_recommendations(self, check_result: CheckResult) -> list[str]:
        items: list[str] = []

        cookies = check_result.cookies
        if cookies and cookies.analyzed and (
            cookies.cookies_before_consent_found
            or (not cookies.banner_found and self._cookie_evidence_found(cookies))
            or (
                (cookies.banner_found or self._cookie_evidence_found(cookies))
                and cookies.interaction_available
                and not cookies.reject_button_found
            )
        ):
            items.append(
                "Проверить наличие и содержание cookie-баннера, включая возможность отклонения необязательных cookies."
            )

        advertising = check_result.advertising
        if advertising and advertising.ad_services_found and (
            not advertising.erid_found or not advertising.ad_marking_found
        ):
            items.append("Проверить рекламные материалы, erid и маркировку рекламы вручную.")

        infrastructure = check_result.infrastructure
        if infrastructure and (
            infrastructure.external_domains_found
            or infrastructure.foreign_services_found
            or infrastructure.analytics_services_found
        ):
            items.append(
                "Проверить условия обработки и передачи данных при использовании сторонних сервисов."
            )
        elif check_result.external_services and check_result.external_services.found:
            items.append(
                "Проверить условия обработки и передачи данных при использовании сторонних сервисов."
            )

        accessibility = check_result.accessibility
        if accessibility and accessibility.issues_found:
            items.append("Проверить найденные технические замечания по доступности.")

        if check_result.security and check_result.security.has_mixed_content:
            items.append("Проверить mixed content и заменить HTTP-ресурсы на HTTPS.")

        owner = check_result.owner_requisites
        if owner and not owner.privacy_email_found:
            items.append(
                "Проверить наличие отдельного контактного адреса для обращений субъектов персональных данных."
            )

        if check_result.policy and (not check_result.policy.found or check_result.policy.candidates):
            items.append(
                "Проверить содержание политики конфиденциальности и согласий на обработку персональных данных."
            )

        if not items:
            items.append(
                "Периодически повторять проверку и отслеживать изменения форм, документов и сторонних сервисов."
            )

        return self._dedupe_text(items)

    def _build_checked_areas(self, check_result: CheckResult) -> list[str]:
        items: list[str] = []

        if check_result.availability is not None:
            items.append("Доступность сайта")
        if check_result.domain_compliance is not None:
            items.append("Доменная зона")
        if check_result.security is not None:
            items.append("HTTPS и mixed content")
        if check_result.forms is not None:
            items.append("Формы и признаки сбора данных")
        if check_result.policy is not None:
            items.append("Политика конфиденциальности")
        if check_result.browser_check and check_result.browser_check.performed:
            items.append("Браузерная проверка страницы")
            items.append("Cookie и сетевые запросы до явного выбора пользователя")
            if (
                check_result.browser_check.cookie_interaction
                and check_result.browser_check.cookie_interaction.enabled
            ):
                items.append("Cookie interaction check")
        if check_result.advertising is not None:
            items.append("Рекламные признаки")
        if check_result.accessibility is not None and check_result.accessibility.checked:
            items.append("Базовая техническая доступность")
        if check_result.infrastructure is not None and check_result.infrastructure.checked:
            items.append("Внешняя инфраструктура и сторонние домены")
        if check_result.owner_requisites is not None:
            items.append("Реквизиты владельца")
        if check_result.external_services is not None:
            items.append("Внешние сервисы")
        if check_result.russian_market is not None:
            items.append("Признаки российского рынка")

        return self._dedupe_text(items)

    def _build_manual_review_required(self, check_result: CheckResult) -> list[str]:
        items: list[str] = []

        if check_result.policy is not None or check_result.forms is not None:
            items.append(
                "Содержание политики конфиденциальности и согласий на обработку персональных данных."
            )

        cookies = check_result.cookies
        if cookies and cookies.analyzed and (
            cookies.cookies_before_consent_found
            or cookies.analytics_requests_before_consent_found
            or cookies.advertising_requests_before_consent_found
        ):
            items.append("Назначение cookies и сторонних сетевых запросов.")
        if cookies and cookies.analyzed and (
            (not cookies.banner_found and self._cookie_evidence_found(cookies))
            or (
                (cookies.banner_found or self._cookie_evidence_found(cookies))
                and cookies.interaction_available
                and not cookies.reject_button_found
            )
        ):
            items.append("Наличие возможности отклонить необязательные cookies.")

        advertising = check_result.advertising
        if advertising and advertising.ad_services_found:
            items.append("Маркировка рекламных материалов и erid.")

        infrastructure = check_result.infrastructure
        if infrastructure and infrastructure.external_domains_found:
            items.append("Условия передачи данных сторонним сервисам.")
        if infrastructure and infrastructure.foreign_services_found:
            items.append("Фактическое место хранения и обработки персональных данных.")

        accessibility = check_result.accessibility
        if accessibility and accessibility.issues_found:
            items.append("Доступность интерфейса по требованиям применимого стандарта.")

        owner = check_result.owner_requisites
        if owner and not owner.privacy_email_found:
            items.append(
                "Наличие отдельного контактного адреса для обращений субъектов персональных данных."
            )

        return self._dedupe_text(items)

    def _build_limitations(self, check_result: CheckResult) -> list[str]:
        items = [
            "Автоматическая проверка не является юридическим заключением.",
            "Результат основан только на проверенных страницах и данных, доступных на момент проверки.",
            "Сервис не определяет фактическое место хранения персональных данных без внешних подтверждающих источников.",
            "Проверка доступности не заменяет полноценный аудит по профильному стандарту.",
        ]
        if check_result.browser_check and check_result.browser_check.performed:
            items.append(
                "Браузерная проверка может отличаться в зависимости от региона, устройства, сессии и состояния сайта."
            )
        else:
            items.append(
                "Браузерная проверка не выполнялась, поэтому cookies, динамические запросы и часть сторонних сервисов могли быть не обнаружены."
            )
        return self._dedupe_text(items)

    def _cookie_evidence_found(self, cookies) -> bool:
        return bool(
            cookies.cookies_before_consent_found
            or cookies.third_party_cookies_before_consent_found
            or cookies.analytics_requests_before_consent_found
            or cookies.advertising_requests_before_consent_found
            or cookies.third_party_requests_before_consent_found
        )

    def _factor_text(self, factors: list[RiskFactor]) -> str:
        labels: list[str] = []
        seen: set[str] = set()
        for factor in factors[:3]:
            label = (factor.message or factor.code).strip().rstrip(".")
            if not label or label in seen:
                continue
            seen.add(label)
            labels.append(label)
        return "; ".join(labels)

    def _dedupe_text(self, items: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _page_word(self, count: int) -> str:
        if count % 10 == 1 and count % 100 != 11:
            return "страница"
        if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
            return "страницы"
        return "страниц"
