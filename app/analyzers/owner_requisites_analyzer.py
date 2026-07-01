import re

from bs4 import BeautifulSoup

from app.schemas.owner_requisites import OwnerRequisiteItem, OwnerRequisitesResult
from app.schemas.pages import PageData


class OwnerRequisitesAnalyzer:
    organization_patterns = (
        re.compile(
            r"\b(?:ООО|ОАО|ПАО|АО)\s*[\"«][^\"»]{2,120}[\"»]",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bФГБОУ\s+ВО\s+[^©\n\r,;]{2,160}",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bОбщество\s+с\s+ограниченной\s+ответственностью\s+[\"«]?[^\"»\n\r,;]{2,120}[\"»]?",
            re.IGNORECASE,
        ),
    )
    person_patterns = (
        re.compile(
            r"\bИндивидуальный\s+предприниматель\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2}",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bИП\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2}",
            re.IGNORECASE,
        ),
    )
    inn_pattern = re.compile(r"\bИНН\s*[:№#-]?\s*(\d{10}|\d{12})\b", re.IGNORECASE)
    ogrn_pattern = re.compile(r"\bОГРН\s*[:№#-]?\s*(\d{13})\b", re.IGNORECASE)
    ogrnip_pattern = re.compile(r"\bОГРНИП\s*[:№#-]?\s*(\d{15})\b", re.IGNORECASE)
    phone_pattern = re.compile(
        r"(?:\+7|8)\s*\(?\d{3}\)?[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}"
    )
    email_pattern = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    privacy_email_prefixes = ("privacy", "personal", "pd", "data", "dpo")
    address_markers = (
        "россия",
        "российская федерация",
        "г.",
        "город",
        "ул.",
        "улица",
        "проспект",
        "область",
        "край",
        "район",
        "офис",
    )
    address_label_pattern = re.compile(
        r"(?:Юридический|Почтовый)\s+адрес\s*:\s*(.{5,220}?)(?=(?:Юридический|Почтовый)\s+адрес\s*:|$)",
        re.IGNORECASE,
    )
    address_stop_patterns = (
        r"©",
        r"\bОГРНИП\b",
        r"\bОГРН\b",
        r"\bИНН\b",
        r"\bWhatsApp\b",
        r"\bТелефон\b",
        r"\bEmail\b",
        r"\bE-mail\b",
        r"\bЭлектронная\s+почта\b",
        r"\bУсловия\b",
        r"\bПолитика\b",
        r"\bКонтакты\b",
        r"\bЮридический\s+адрес\b",
        r"\bПочтовый\s+адрес\b",
        r"\bcopyright\b",
    )
    weak_address_markers = ("рф",)
    postal_index_pattern = re.compile(r"\b\d{6}\b")
    owner_conflict_warning = (
        "На проверенных страницах обнаружены разные упоминания организаций; требуется ручная проверка владельца сайта."
    )
    reliable_page_markers = (
        "contact",
        "contacts",
        "kontakty",
        "about",
        "privacy",
        "policy",
        "legal",
        "requisites",
        "rekviz",
        "sveden",
    )
    reliable_attr_markers = (
        "footer",
        "copyright",
        "contact",
        "contacts",
        "about",
        "requisites",
        "rekviz",
        "legal",
        "privacy",
        "policy",
    )
    requisites_context_markers = ("ИНН", "ОГРН", "ОГРНИП", "реквизит", "сведения об организации")

    def analyze(self, pages: list[PageData]) -> OwnerRequisitesResult:
        items: list[OwnerRequisiteItem] = []
        warnings: list[str] = []
        seen: set[tuple[str, str, str]] = set()
        organization_candidates: list[OwnerRequisiteItem] = []
        organization_seen: set[tuple[str, str, str]] = set()

        for page in pages:
            if not page.html:
                continue

            page_url = page.final_url or page.url
            soup = BeautifulSoup(page.html, "html.parser")
            text = self._page_text(page.html)

            self._find_organization_candidates(soup, page_url, organization_candidates, organization_seen)
            self._find_first(self.person_patterns, text, "person_name", page_url, items, seen)
            self._find_group(self.inn_pattern, text, "inn", page_url, items, seen)
            self._find_group(self.ogrnip_pattern, text, "ogrnip", page_url, items, seen)
            self._find_group(self.ogrn_pattern, text, "ogrn", page_url, items, seen)
            self._find_full(self.phone_pattern, text, "phone", page_url, items, seen)
            self._find_emails(text, page_url, items, seen)
            self._find_address(text, page_url, items, seen, warnings)

        manual_check_required = self._apply_organization_choice(
            organization_candidates,
            items,
            seen,
            warnings,
        )
        return self._build_result(items, warnings, manual_check_required)

    def _page_text(self, html: str) -> str:
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        return re.sub(r"\s+", " ", text)

    def _find_first(
        self,
        patterns: tuple[re.Pattern[str], ...],
        text: str,
        field_type: str,
        page_url: str,
        items: list[OwnerRequisiteItem],
        seen: set[tuple[str, str, str]],
    ) -> None:
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                self._append_item(items, seen, field_type, match.group(0), page_url, match.group(0))
                return

    def _find_organization_candidates(
        self,
        soup: BeautifulSoup,
        page_url: str,
        items: list[OwnerRequisiteItem],
        seen: set[tuple[str, str, str]],
    ) -> None:
        for text in self._reliable_owner_texts(soup, page_url):
            for pattern in self.organization_patterns:
                for match in pattern.finditer(text):
                    self._append_item(
                        items,
                        seen,
                        "organization_name",
                        match.group(0),
                        page_url,
                        match.group(0),
                    )

    def _reliable_owner_texts(self, soup: BeautifulSoup, page_url: str) -> list[str]:
        texts: list[str] = []
        for tag in soup.find_all(["footer"]):
            texts.append(tag.get_text(" ", strip=True))

        for tag in soup.find_all(True):
            attrs = " ".join(
                str(value)
                for value in [tag.get("id"), tag.get("class")]
                if value
            ).lower()
            if any(marker in attrs for marker in self.reliable_attr_markers):
                texts.append(tag.get_text(" ", strip=True))

        page_url_lowered = page_url.lower()
        if any(marker in page_url_lowered for marker in self.reliable_page_markers):
            texts.append(soup.get_text(" ", strip=True))

        page_text = soup.get_text(" ", strip=True)
        if self.inn_pattern.search(page_text) or self.ogrn_pattern.search(page_text) or self.ogrnip_pattern.search(page_text):
            texts.append(page_text)

        for tag in soup.find_all(True):
            text = tag.get_text(" ", strip=True)
            if any(marker.lower() in text.lower() for marker in self.requisites_context_markers):
                texts.append(text)

        deduped: list[str] = []
        seen: set[str] = set()
        for text in texts:
            normalized = re.sub(r"\s+", " ", text).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        return deduped

    def _apply_organization_choice(
        self,
        candidates: list[OwnerRequisiteItem],
        items: list[OwnerRequisiteItem],
        seen: set[tuple[str, str, str]],
        warnings: list[str],
    ) -> bool:
        organization_values = {
            self._normalize_org_name(candidate.value): candidate
            for candidate in candidates
            if self._normalize_org_name(candidate.value)
        }
        if not organization_values:
            return False
        if len(organization_values) > 1:
            if self.owner_conflict_warning not in warnings:
                warnings.append(self.owner_conflict_warning)
            return True

        candidate = next(iter(organization_values.values()))
        self._append_item(
            items,
            seen,
            "organization_name",
            candidate.value,
            candidate.page_url,
            candidate.evidence,
        )
        return False

    def _normalize_org_name(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip().lower()
        normalized = normalized.replace("«", "\"").replace("»", "\"")
        return normalized

    def _find_group(
        self,
        pattern: re.Pattern[str],
        text: str,
        field_type: str,
        page_url: str,
        items: list[OwnerRequisiteItem],
        seen: set[tuple[str, str, str]],
    ) -> None:
        match = pattern.search(text)
        if not match:
            return
        self._append_item(items, seen, field_type, match.group(1), page_url, match.group(0))

    def _find_full(
        self,
        pattern: re.Pattern[str],
        text: str,
        field_type: str,
        page_url: str,
        items: list[OwnerRequisiteItem],
        seen: set[tuple[str, str, str]],
    ) -> None:
        match = pattern.search(text)
        if not match:
            return
        self._append_item(items, seen, field_type, match.group(0), page_url, match.group(0))

    def _find_emails(
        self,
        text: str,
        page_url: str,
        items: list[OwnerRequisiteItem],
        seen: set[tuple[str, str, str]],
    ) -> None:
        for match in self.email_pattern.finditer(text):
            value = match.group(0)
            local_part = value.split("@", 1)[0].lower()
            field_type = (
                "privacy_email"
                if local_part in self.privacy_email_prefixes
                else "email"
            )
            self._append_item(items, seen, field_type, value, page_url, value)

    def _find_address(
        self,
        text: str,
        page_url: str,
        items: list[OwnerRequisiteItem],
        seen: set[tuple[str, str, str]],
        warnings: list[str],
    ) -> None:
        lowered = text.lower()
        labeled_addresses = self._labeled_addresses(text)
        if labeled_addresses:
            for labeled_address in labeled_addresses:
                self._append_address(items, seen, labeled_address, page_url, labeled_address)
            return

        strong_matches = [marker for marker in self.address_markers if marker in lowered]
        has_postal_index = bool(self.postal_index_pattern.search(text))
        has_weak_only = any(
            re.search(rf"\b{re.escape(marker)}\b", lowered)
            for marker in self.weak_address_markers
        )

        if strong_matches or has_postal_index:
            evidence = self._address_evidence(text, strong_matches, has_postal_index)
            self._append_address(items, seen, evidence, page_url, evidence)
            return

        if has_weak_only:
            warning = "Found weak address marker 'РФ' without additional address details."
            if warning not in warnings:
                warnings.append(warning)

    def _address_evidence(
        self,
        text: str,
        markers: list[str],
        has_postal_index: bool,
    ) -> str:
        if has_postal_index:
            match = self.postal_index_pattern.search(text)
            if match:
                return self._compact_fragment(text, match.start(), match.end())

        marker = markers[0]
        index = text.lower().find(marker)
        return self._compact_fragment(text, index, index + len(marker))

    def _labeled_addresses(self, text: str) -> list[str]:
        return [
            cleaned
            for match in self.address_label_pattern.finditer(text)
            if (cleaned := self._clean_address(match.group(1)))
        ]

    def _compact_fragment(self, text: str, start: int, end: int) -> str:
        left_boundaries = ("\n", "\r", ";", "|")
        right_boundaries = ("\n", "\r", ";", "|")
        window_start = max(max(text.rfind(boundary, 0, start) for boundary in left_boundaries) + 1, 0)
        right_positions = [
            position
            for boundary in right_boundaries
            if (position := text.find(boundary, end)) != -1
        ]
        window_end = min(right_positions) if right_positions else min(start + 120, len(text))

        fragment = text[window_start:window_end]
        if len(fragment) > 140:
            fragment = text[start: min(start + 120, len(text))]

        return self._clean_address(fragment)

    def _clean_address(self, value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip(" ,;:-")
        value = re.sub(
            r"^(?:контакты|адрес|юридический адрес|почтовый адрес)\s*:\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )

        stop_positions: list[int] = []
        for pattern in (*self.address_stop_patterns, self.email_pattern.pattern, self.phone_pattern.pattern):
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                stop_positions.append(match.start())

        if stop_positions:
            value = value[: min(stop_positions)]

        value = value.strip(" ,;:-.")
        if len(value) > 120:
            truncated = value[:120]
            comma_position = truncated.rfind(",")
            value = truncated[:comma_position] if comma_position >= 40 else truncated

        return value.strip(" ,;:-.")

    def _append_address(
        self,
        items: list[OwnerRequisiteItem],
        seen: set[tuple[str, str, str]],
        value: str,
        page_url: str,
        evidence: str | None,
    ) -> None:
        cleaned = self._clean_address(value)
        if not self._is_plausible_address(cleaned):
            return

        self._append_item(items, seen, "address", cleaned, page_url, cleaned if evidence else None)

    def _is_plausible_address(self, value: str) -> bool:
        if len(value) < 10 or len(value) > 120:
            return False

        lowered = value.lower()
        has_marker = any(marker in lowered for marker in self.address_markers)
        return has_marker or bool(self.postal_index_pattern.search(value))

    def _append_item(
        self,
        items: list[OwnerRequisiteItem],
        seen: set[tuple[str, str, str]],
        field_type: str,
        value: str,
        page_url: str,
        evidence: str | None,
    ) -> None:
        normalized_value = re.sub(r"\s+", " ", value).strip()
        key = (field_type, normalized_value.lower(), page_url)
        if not normalized_value or key in seen:
            return

        seen.add(key)
        items.append(
            OwnerRequisiteItem(
                field_type=field_type,
                value=normalized_value,
                page_url=page_url,
                evidence=evidence,
            )
        )

    def _build_result(
        self,
        items: list[OwnerRequisiteItem],
        warnings: list[str],
        manual_check_required: bool = False,
    ) -> OwnerRequisitesResult:
        return OwnerRequisitesResult(
            found=bool(items),
            organization_name=self._first_value(items, "organization_name"),
            person_name=self._first_value(items, "person_name"),
            inn=self._first_value(items, "inn"),
            ogrn=self._first_value(items, "ogrn"),
            ogrnip=self._first_value(items, "ogrnip"),
            address_found=self._has_item(items, "address"),
            phone_found=self._has_item(items, "phone"),
            email_found=self._has_item(items, "email") or self._has_item(items, "privacy_email"),
            privacy_email_found=self._has_item(items, "privacy_email"),
            manual_check_required=manual_check_required,
            items=items,
            warnings=warnings,
        )

    def _first_value(self, items: list[OwnerRequisiteItem], field_type: str) -> str | None:
        for item in items:
            if item.field_type == field_type:
                return item.value
        return None

    def _has_item(self, items: list[OwnerRequisiteItem], field_type: str) -> bool:
        return any(item.field_type == field_type for item in items)
