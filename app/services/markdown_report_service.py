import re
from html import unescape
from typing import Iterable

from app.schemas.check import CheckResult


class MarkdownReportService:
    evidence_limit = 5
    evidence_item_limit = 300
    infrastructure_domain_limit = 10
    forbidden_phrases = (
        "сайт нарушает закон",
        "сайт незаконен",
        "нарушение 152-фз",
        "нарушение закона о рекламе",
        "данные хранятся за границей",
        "сайт не соответствует гост",
        "реклама оформлена неправильно",
        "согласие отсутствует",
    )

    def build(self, result: CheckResult) -> str:
        sections: list[str] = [
            "# Отчёт по проверке сайта",
            "",
            self._header(result),
            "",
            self._list_section("Краткие выводы", result.report.summary if result.report else []),
            self._list_section("Рекомендации", result.report.recommendations if result.report else [], ordered=False),
            self._list_section("Что проверялось автоматически", result.report.checked_areas if result.report else [], ordered=False),
            self._list_section("Что требует ручной проверки", result.report.manual_review_required if result.report else [], ordered=False),
            self._list_section("Ограничения проверки", result.report.limitations if result.report else [], ordered=False),
            self._risk_section(result),
            self._cookies_section(result),
            self._advertising_section(result),
            self._accessibility_section(result),
            self._infrastructure_section(result),
            self._owner_requisites_section(result),
            self._domain_section(result),
            self._technical_section(result),
        ]
        markdown = "\n".join(section for section in sections if section is not None)
        return self._remove_forbidden_phrases(markdown).strip() + "\n"

    def _header(self, result: CheckResult) -> str:
        risk = result.risk_assessment
        checked_at = result.check.checked_at.isoformat()
        return "\n".join(
            [
                f"**Сайт:** {self._clean(result.site.final_url or result.site.normalized_url)}  ",
                f"**Домен:** {self._clean(result.site.domain)}  ",
                f"**Статус проверки:** {self._clean(result.check.status)}  ",
                f"**Дата проверки:** {self._clean(checked_at)}  ",
                f"**Уровень риска:** {self._clean(risk.level if risk else 'unknown')}  ",
                f"**Итоговый балл:** {risk.total_score if risk else 0} / 100  ",
            ]
        )

    def _list_section(self, title: str, items: Iterable[str], ordered: bool = True) -> str:
        cleaned = self._dedupe_text(self._clean(item) for item in items if self._clean(item))
        if not cleaned:
            cleaned = ["Нет данных для отображения."]
        lines = [f"## {title}", ""]
        for index, item in enumerate(cleaned, start=1):
            prefix = f"{index}. " if ordered else "- "
            lines.append(f"{prefix}{item}")
        return "\n".join(lines) + "\n"

    def _risk_section(self, result: CheckResult) -> str:
        risk = result.risk_assessment
        lines = ["## Основные риск-факторы", ""]
        if not risk or not risk.factors:
            lines.append("Существенные риск-факторы автоматически не обнаружены.")
            return "\n".join(lines) + "\n"

        lines.extend(
            [
                "| Уровень | Код | Описание | Балл |",
                "|---|---|---|---|",
            ]
        )
        for factor in risk.factors[:10]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._table_cell(factor.level),
                        self._table_cell(factor.code),
                        self._table_cell(factor.message),
                        str(factor.score),
                    ]
                )
                + " |"
            )

        evidence = []
        for factor in risk.factors:
            for item in factor.evidence:
                cleaned = self._clean(item, limit=self.evidence_item_limit)
                if cleaned:
                    evidence.append(cleaned)
                if len(evidence) >= self.evidence_limit:
                    break
            if len(evidence) >= self.evidence_limit:
                break
        if evidence:
            lines.extend(["", "Примеры evidence:"])
            lines.extend(f"- {item}" for item in evidence)
        return "\n".join(lines) + "\n"

    def _cookies_section(self, result: CheckResult) -> str:
        cookies = result.cookies
        if not cookies:
            return ""
        lines = ["## Cookie и согласия", ""]
        lines.extend(
            [
                f"- Cookie анализ выполнен: {self._yes_no(cookies.analyzed)}",
                f"- Cookie-баннер найден автоматически: {self._yes_no(cookies.banner_found)}",
                f"- Кнопка принятия найдена автоматически: {self._yes_no(cookies.accept_button_found)}",
                f"- Кнопка отклонения найдена автоматически: {self._yes_no(cookies.reject_button_found)}",
                f"- Обнаружены признаки cookies до явного выбора пользователя: {self._yes_no(cookies.cookies_before_consent_found)}",
                f"- Обнаружены признаки сторонних cookies: {self._yes_no(cookies.third_party_cookies_before_consent_found)}",
                f"- Обнаружены признаки аналитических запросов до выбора: {self._yes_no(cookies.analytics_requests_before_consent_found)}",
                f"- Обнаружены признаки рекламных запросов до выбора: {self._yes_no(cookies.advertising_requests_before_consent_found)}",
                f"- Обнаружены признаки сторонних сетевых запросов до выбора: {self._yes_no(cookies.third_party_requests_before_consent_found)}",
            ]
        )
        warnings = self._dedupe_text(self._clean(warning) for warning in cookies.warnings if self._clean(warning))
        if warnings:
            lines.extend(["", "Предупреждения:"])
            lines.extend(f"- {warning}" for warning in warnings[:5])
        return "\n".join(lines) + "\n"

    def _advertising_section(self, result: CheckResult) -> str:
        advertising = result.advertising
        if not advertising:
            return ""
        lines = ["## Реклама", ""]
        if not advertising.found:
            lines.append("На проверенных страницах явные рекламные признаки автоматически не обнаружены.")
        lines.extend(
            [
                f"- Признаки рекламных сервисов найдены: {self._yes_no(advertising.ad_services_found)}",
                f"- erid найден автоматически: {self._yes_no(advertising.erid_found)}",
                f"- Маркировка рекламы найдена автоматически: {self._yes_no(advertising.ad_marking_found)}",
            ]
        )
        warnings = self._dedupe_text(self._clean(warning) for warning in advertising.warnings if self._clean(warning))
        if warnings:
            lines.extend(["", "Предупреждения:"])
            lines.extend(f"- {warning}" for warning in warnings[:5])
        return "\n".join(lines) + "\n"

    def _accessibility_section(self, result: CheckResult) -> str:
        accessibility = result.accessibility
        if not accessibility:
            return ""
        lines = [
            "## Доступность",
            "",
            f"- Проверка выполнена: {self._yes_no(accessibility.checked)}",
            f"- Обнаружены технические признаки возможных проблем доступности: {self._yes_no(accessibility.issues_found)}",
            f"- Изображения без alt: {accessibility.missing_alt_count}",
            f"- Пустые ссылки: {accessibility.empty_links_count}",
            f"- Поля ввода без label: {accessibility.missing_input_labels_count}",
            f"- iframe без title: {accessibility.iframe_missing_title_count}",
            f"- Дублирующиеся id: {accessibility.duplicate_ids_count}",
        ]
        if accessibility.issues_found:
            lines.append("- Требуется ручная проверка найденных технических признаков.")
        return "\n".join(lines) + "\n"

    def _infrastructure_section(self, result: CheckResult) -> str:
        infrastructure = result.infrastructure
        if not infrastructure:
            return ""
        lines = [
            "## Инфраструктура и сторонние сервисы",
            "",
            f"- Проверка выполнена: {self._yes_no(infrastructure.checked)}",
            f"- Всего доменов: {infrastructure.domains_count}",
            f"- Обнаружены признаки сторонних доменов: {self._yes_no(infrastructure.external_domains_found)}",
            f"- Обнаружены признаки использования иностранных сервисов: {self._yes_no(infrastructure.foreign_services_found)}",
            f"- Аналитические сервисы: {self._yes_no(infrastructure.analytics_services_found)}",
            f"- Рекламные сервисы: {self._yes_no(infrastructure.advertising_services_found)}",
            f"- Видео-сервисы: {self._yes_no(infrastructure.video_services_found)}",
            f"- Шрифтовые сервисы: {self._yes_no(infrastructure.fonts_services_found)}",
            f"- Платёжные сервисы: {self._yes_no(infrastructure.payment_services_found)}",
            f"- CRM-сервисы: {self._yes_no(infrastructure.crm_services_found)}",
            "- Автоматическая проверка не определяет фактическое место хранения данных.",
        ]
        domains = [
            self._clean(domain.domain)
            for domain in infrastructure.domains
            if domain.is_third_party and self._clean(domain.domain)
        ][: self.infrastructure_domain_limit]
        if domains:
            lines.extend(["", "Примеры сторонних доменов:"])
            lines.extend(f"- {domain}" for domain in domains)
        return "\n".join(lines) + "\n"

    def _owner_requisites_section(self, result: CheckResult) -> str:
        owner = result.owner_requisites
        if not owner:
            return ""
        lines = ["## Реквизиты владельца", ""]
        if not owner.found:
            lines.append("На проверенных страницах реквизиты владельца не найдены автоматически.")
        organization = (
            "требуется ручная проверка"
            if owner.manual_check_required or not owner.organization_name
            else self._clean(owner.organization_name)
        )
        lines.extend(
            [
                f"- Реквизиты найдены автоматически: {self._yes_no(owner.found)}",
                f"- Организация: {organization}",
                f"- ИНН: {self._clean(owner.inn) or 'не найдено автоматически'}",
                f"- ОГРН: {self._clean(owner.ogrn) or 'не найдено автоматически'}",
                f"- Телефон найден: {self._yes_no(owner.phone_found)}",
                f"- Email найден: {self._yes_no(owner.email_found)}",
                f"- Адрес найден: {self._yes_no(owner.address_found)}",
                f"- Отдельный privacy email найден: {self._yes_no(owner.privacy_email_found)}",
            ]
        )
        return "\n".join(lines) + "\n"

    def _domain_section(self, result: CheckResult) -> str:
        domain = result.domain_compliance
        if not domain:
            return ""
        lines = [
            "## Доменная зона",
            "",
            f"- Зона: {self._clean(domain.zone) or 'не определена'}",
            f"- Требование применимо к зоне: {self._yes_no(domain.applies_to_domain_zone)}",
            f"- Требуется идентификация через ЕСИА: {self._yes_no(domain.esia_identification_required)}",
            f"- Статус: {self._clean(domain.status)}",
        ]
        if domain.message:
            lines.append(f"- Сообщение: {self._clean(domain.message)}")
        return "\n".join(lines) + "\n"

    def _technical_section(self, result: CheckResult) -> str:
        availability = result.availability
        security = result.security
        browser = result.browser_check
        pages_checked = result.pages.total_checked if result.pages else 0
        lines = [
            "## Технические детали",
            "",
            f"- HTTP status availability: {availability.status_code if availability else 'нет данных'}",
            f"- HTTPS включён: {self._yes_no(security.https_enabled) if security else 'нет данных'}",
            f"- Mixed content найден: {self._yes_no(security.has_mixed_content) if security else 'нет данных'}",
            f"- Browser check включён: {self._yes_no(browser.enabled) if browser else 'нет данных'}",
            f"- Browser check выполнен: {self._yes_no(browser.performed) if browser else 'нет данных'}",
            f"- Проверено страниц: {pages_checked}",
            f"- Длительность проверки: {result.check.duration_ms} ms",
        ]
        return "\n".join(lines) + "\n"

    def _yes_no(self, value: bool | None) -> str:
        if value is None:
            return "нет данных"
        return "да" if value else "нет"

    def _table_cell(self, value: str | None) -> str:
        return self._clean(value).replace("|", "\\|")

    def _dedupe_text(self, values: Iterable[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = self._clean(value)
            normalized = re.sub(r"\s+", " ", cleaned).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(cleaned)
        return deduped

    def _clean(self, value: object, limit: int = evidence_item_limit) -> str:
        if value is None:
            return ""
        text = unescape(str(value))
        if re.search(r"<\s*(html|body|script|style)\b", text, flags=re.IGNORECASE):
            return "html content omitted"
        text = re.sub(r"data:image/[a-zA-Z0-9.+-]+;base64,[a-zA-Z0-9+/=\s]+", "inline data image", text)
        text = re.sub(r"\b[A-Za-z0-9+/]{120,}={0,2}\b", "[base64 omitted]", text)
        text = re.sub(r"<[^>\n]{1,500}>", "", text)
        text = " ".join(text.split())
        if len(text) > limit:
            text = text[:limit].rstrip() + "..."
        return text

    def _remove_forbidden_phrases(self, markdown: str) -> str:
        result = markdown
        for phrase in self.forbidden_phrases:
            result = re.sub(re.escape(phrase), "", result, flags=re.IGNORECASE)
        return result
