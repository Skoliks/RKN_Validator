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
        "cookie_banner_not_found": "cookie-баннер не найден или не распознан автоматически при наличии cookie-признаков",
        "cookies_before_consent_detected": "обнаружены признаки cookies или аналитических запросов до выбора пользователя",
        "advertising_before_consent_detected": "обнаружены запросы к рекламным сервисам до выбора пользователя",
        "cookie_reject_button_not_found": "явная кнопка отклонения cookie не найдена автоматически",
        "cookie_reject_did_not_reduce_tracking": "после отклонения не зафиксировано заметного снижения tracking-запросов",
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

        if check_result.accessibility:
            if check_result.accessibility.issues_found:
                sentences.append(
                    "Обнаружены признаки возможных технических проблем доступности; требуется ручная проверка."
                )
                if check_result.accessibility.missing_alt_count > 0:
                    sentences.append(
                        "На проверенных страницах найдены изображения без атрибута alt."
                    )
                if (
                    check_result.accessibility.empty_links_count > 0
                    or check_result.accessibility.empty_buttons_count > 0
                ):
                    sentences.append(
                        "Найдены ссылки или кнопки без доступного текстового описания."
                    )
                if check_result.accessibility.missing_input_labels_count > 0:
                    sentences.append("Найдены поля форм без автоматически определённой подписи.")
            else:
                sentences.append(
                    "Явные технические замечания по доступности на проверенных страницах не найдены."
                )

        if check_result.advertising:
            if check_result.advertising.ad_services_found:
                sentences.append("Обнаружены признаки подключения рекламных сервисов.")
                if not check_result.advertising.erid_found:
                    sentences.append(
                        "На проверенных страницах не найден erid; требуется ручная проверка рекламных материалов."
                    )
                if not check_result.advertising.ad_marking_found:
                    sentences.append("Явная маркировка рекламы не была найдена автоматически.")
            elif not check_result.advertising.found:
                sentences.append("Явные рекламные признаки на проверенных страницах не найдены.")

        if check_result.cookies and check_result.cookies.analyzed:
            if check_result.cookies.cookies_before_consent_found:
                sentences.append(
                    "На момент браузерной проверки обнаружены cookies после первичной загрузки страницы до явного выбора пользователя."
                )
            if (
                check_result.cookies.analytics_requests_before_consent_found
                or check_result.cookies.advertising_requests_before_consent_found
            ):
                sentences.append(
                    "Также обнаружены запросы к аналитическим или рекламным сервисам до явного выбора пользователя."
                )
            if not check_result.cookies.banner_found:
                sentences.append(
                    "Cookie-баннер не был найден или не был распознан автоматически; требуется ручная проверка."
                )
            if check_result.cookies.interaction_available and not check_result.cookies.reject_button_found:
                sentences.append(
                    "Явная кнопка отклонения cookie не была найдена автоматически; требуется ручная проверка."
                )
            if check_result.cookies.reject_test_performed:
                if (
                    check_result.cookies.analytics_reduced_after_reject is False
                    or check_result.cookies.advertising_reduced_after_reject is False
                ):
                    sentences.append(
                        "После нажатия кнопки отклонения не зафиксировано заметного снижения cookies или запросов к сервисам отслеживания; требуется ручная проверка."
                    )
                elif (
                    check_result.cookies.cookies_reduced_after_reject
                    or check_result.cookies.analytics_reduced_after_reject
                    or check_result.cookies.advertising_reduced_after_reject
                ):
                    sentences.append(
                        "После нажатия кнопки отклонения количество cookies или запросов к сервисам отслеживания уменьшилось."
                    )

        if check_result.domain_compliance:
            if check_result.domain_compliance.applies_to_domain_zone:
                sentences.append(
                    "Домен находится в зоне, для которой требуется ручная проверка идентификации администратора через ЕСИА."
                )
            elif check_result.domain_compliance.status == "not_applicable":
                sentences.append(
                    "Требование идентификации администратора через ЕСИА к данной доменной зоне не применяется."
                )

        if check_result.owner_requisites and check_result.owner_requisites.found:
            if check_result.owner_requisites.inn and check_result.owner_requisites.ogrn:
                sentences.append("На проверенных страницах найдены ИНН и ОГРН владельца сайта.")
            else:
                sentences.append("На проверенных страницах найдены отдельные реквизиты владельца сайта.")
        elif check_result.owner_requisites is not None:
            sentences.append(
                "На проверенных страницах не удалось автоматически выделить реквизиты владельца сайта."
            )

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

        if check_result.security and check_result.security.has_mixed_content:
            sentences.append(
                "Также обнаружено подключение ресурса по незащищённому протоколу HTTP на HTTPS-странице."
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
        return " ".join(sentences[:12])

    def _build_recommendation(self, check_result: CheckResult) -> str:
        risk = check_result.risk_assessment
        level = risk.level if risk else "low"
        factor_codes = {factor.code for factor in risk.factors} if risk else set()

        if self._has_only_external_services_without_forms(check_result):
            return self._with_privacy_email_recommendation(
                check_result,
                "Общий риск низкий. Рекомендуется вручную проверить назначение "
                "сторонних сервисов и условия передачи данных.",
            )

        if level == "high":
            return self._with_privacy_email_recommendation(
                check_result,
                "Рекомендуется провести ручную проверку и доработать документы, формы "
                "и сторонние сервисы по найденным признакам. Особое внимание стоит "
                "уделить передаче данных через формы и внешним провайдерам.",
            )

        if level == "medium":
            if {
                "accessibility_medium_issues_detected",
                "accessibility_low_issues_detected",
            } & factor_codes:
                return self._with_privacy_email_recommendation(
                    check_result,
                    "Рекомендуется вручную проверить найденные технические замечания по доступности. "
                    "Автоматическая проверка не заменяет полноценный аудит доступности.",
                )
            if {
                "advertising_service_without_erid",
                "advertising_service_without_label",
                "possible_ad_blocks_detected",
            } & factor_codes:
                return self._with_privacy_email_recommendation(
                    check_result,
                    "Рекомендуется вручную проверить рекламные материалы, найденные рекламные сервисы, erid и маркировку рекламы. "
                    "Автоматическая проверка не подтверждает и не исключает нарушение.",
                )
            if "foreign_analytics_detected" in factor_codes or "external_resource_detected" in factor_codes:
                return self._with_privacy_email_recommendation(
                    check_result,
                    "Рекомендуется вручную проверить замечания по сторонним сервисам "
                    "и документам сайта.",
                )
            return self._with_privacy_email_recommendation(
                check_result,
                "Рекомендуется вручную проверить найденные замечания и при необходимости "
                "уточнить документы сайта.",
            )

        return self._with_privacy_email_recommendation(
            check_result,
            "Рекомендуется периодически повторять проверку и отслеживать изменения форм, "
            "документов и сторонних сервисов.",
        )

    def _with_privacy_email_recommendation(
        self,
        check_result: CheckResult,
        recommendation: str,
    ) -> str:
        owner_requisites = check_result.owner_requisites
        if owner_requisites is None or owner_requisites.privacy_email_found:
            return recommendation
        return (
            f"{recommendation} Рекомендуется вручную проверить наличие отдельного e-mail "
            "для запросов субъектов персональных данных."
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
