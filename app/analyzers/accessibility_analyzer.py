from collections import Counter

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.accessibility import AccessibilityAnalysisResult, AccessibilityIssueItem
from app.schemas.pages import PageData


class AccessibilityAnalyzer:
    max_items = 100
    evidence_limit = 300
    button_input_types = {"submit", "button", "reset"}
    excluded_input_types = {"hidden", *button_input_types}

    def analyze(self, pages: list[PageData] | None) -> AccessibilityAnalysisResult:
        items: list[AccessibilityIssueItem] = []
        truncated = False
        counts = {
            "missing_alt_count": 0,
            "empty_alt_count": 0,
            "empty_links_count": 0,
            "empty_buttons_count": 0,
            "missing_input_labels_count": 0,
            "iframe_missing_title_count": 0,
            "heading_order_warnings_count": 0,
            "duplicate_ids_count": 0,
        }
        missing_lang = False

        for page in pages or []:
            if not page.html:
                continue

            page_url = page.final_url or page.url
            soup = BeautifulSoup(page.html, "html.parser")

            if self._missing_html_lang(soup):
                missing_lang = True
                truncated = self._add_issue(
                    items,
                    AccessibilityIssueItem(
                        issue_type="missing_html_lang",
                        page_url=page_url,
                        element="html",
                        evidence="<html>",
                        severity="medium",
                    ),
                ) or truncated

            truncated = self._check_images(soup, page_url, items, counts) or truncated
            truncated = self._check_links(soup, page_url, items, counts) or truncated
            truncated = self._check_buttons(soup, page_url, items, counts) or truncated
            truncated = self._check_inputs(soup, page_url, items, counts) or truncated
            truncated = self._check_iframes(soup, page_url, items, counts) or truncated
            truncated = self._check_headings(soup, page_url, items, counts) or truncated
            truncated = self._check_duplicate_ids(soup, page_url, items, counts) or truncated

        issues_found = missing_lang or any(count > 0 for count in counts.values())
        return AccessibilityAnalysisResult(
            checked=True,
            issues_found=issues_found,
            missing_lang=missing_lang,
            missing_alt_count=counts["missing_alt_count"],
            empty_alt_count=counts["empty_alt_count"],
            empty_links_count=counts["empty_links_count"],
            empty_buttons_count=counts["empty_buttons_count"],
            missing_input_labels_count=counts["missing_input_labels_count"],
            iframe_missing_title_count=counts["iframe_missing_title_count"],
            heading_order_warnings_count=counts["heading_order_warnings_count"],
            duplicate_ids_count=counts["duplicate_ids_count"],
            items=items,
            warnings=self._warnings(issues_found, truncated),
        )

    def _missing_html_lang(self, soup: BeautifulSoup) -> bool:
        html = soup.find("html")
        if not isinstance(html, Tag):
            return True
        lang = html.get("lang")
        return not isinstance(lang, str) or not lang.strip()

    def _check_images(
        self,
        soup: BeautifulSoup,
        page_url: str,
        items: list[AccessibilityIssueItem],
        counts: dict[str, int],
    ) -> bool:
        truncated = False
        for img in soup.find_all("img"):
            if not isinstance(img, Tag):
                continue

            if not img.has_attr("alt"):
                counts["missing_alt_count"] += 1
                truncated = self._add_issue(
                    items,
                    self._issue(
                        "missing_image_alt",
                        page_url,
                        img,
                        self._attr_or_element(img, "src"),
                        "medium",
                    ),
                ) or truncated
            elif not str(img.get("alt", "")).strip():
                counts["empty_alt_count"] += 1
                truncated = self._add_issue(
                    items,
                    self._issue(
                        "empty_image_alt",
                        page_url,
                        img,
                        self._attr_or_element(img, "src"),
                        "low",
                    ),
                ) or truncated
        return truncated

    def _check_links(
        self,
        soup: BeautifulSoup,
        page_url: str,
        items: list[AccessibilityIssueItem],
        counts: dict[str, int],
    ) -> bool:
        truncated = False
        for link in soup.find_all("a"):
            if not isinstance(link, Tag):
                continue
            if self._accessible_text(link):
                continue
            if link.find("img", alt=lambda value: isinstance(value, str) and bool(value.strip())):
                continue

            counts["empty_links_count"] += 1
            truncated = self._add_issue(
                items,
                self._issue(
                    "empty_link_text",
                    page_url,
                    link,
                    self._attr_or_element(link, "href"),
                    "medium",
                ),
            ) or truncated
        return truncated

    def _check_buttons(
        self,
        soup: BeautifulSoup,
        page_url: str,
        items: list[AccessibilityIssueItem],
        counts: dict[str, int],
    ) -> bool:
        truncated = False
        for button in soup.find_all("button"):
            if not isinstance(button, Tag) or self._accessible_text(button):
                continue

            counts["empty_buttons_count"] += 1
            truncated = self._add_issue(
                items,
                self._issue("empty_button_text", page_url, button, self._element_html(button), "medium"),
            ) or truncated

        for input_tag in soup.find_all("input"):
            if not isinstance(input_tag, Tag):
                continue
            input_type = self._input_type(input_tag)
            if input_type not in self.button_input_types:
                continue
            if self._accessible_text(input_tag) or str(input_tag.get("value", "")).strip():
                continue

            counts["empty_buttons_count"] += 1
            truncated = self._add_issue(
                items,
                self._issue(
                    "empty_button_text",
                    page_url,
                    input_tag,
                    self._element_html(input_tag),
                    "medium",
                ),
            ) or truncated
        return truncated

    def _check_inputs(
        self,
        soup: BeautifulSoup,
        page_url: str,
        items: list[AccessibilityIssueItem],
        counts: dict[str, int],
    ) -> bool:
        truncated = False
        for field in soup.find_all(["input", "select", "textarea"]):
            if not isinstance(field, Tag):
                continue
            if field.name == "input" and self._input_type(field) in self.excluded_input_types:
                continue
            if self._has_field_label(field, soup):
                continue

            counts["missing_input_labels_count"] += 1
            truncated = self._add_issue(
                items,
                self._issue(
                    "missing_input_label",
                    page_url,
                    field,
                    self._attr_or_element(field, "name"),
                    "medium",
                ),
            ) or truncated
        return truncated

    def _check_iframes(
        self,
        soup: BeautifulSoup,
        page_url: str,
        items: list[AccessibilityIssueItem],
        counts: dict[str, int],
    ) -> bool:
        truncated = False
        for iframe in soup.find_all("iframe"):
            if not isinstance(iframe, Tag):
                continue
            title = iframe.get("title")
            if isinstance(title, str) and title.strip():
                continue

            counts["iframe_missing_title_count"] += 1
            truncated = self._add_issue(
                items,
                self._issue(
                    "iframe_missing_title",
                    page_url,
                    iframe,
                    self._attr_or_element(iframe, "src"),
                    "medium",
                ),
            ) or truncated
        return truncated

    def _check_headings(
        self,
        soup: BeautifulSoup,
        page_url: str,
        items: list[AccessibilityIssueItem],
        counts: dict[str, int],
    ) -> bool:
        truncated = False
        headings = [
            tag
            for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            if isinstance(tag, Tag)
        ]
        if headings and not any(tag.name == "h1" for tag in headings):
            counts["heading_order_warnings_count"] += 1
            truncated = self._add_issue(
                items,
                AccessibilityIssueItem(
                    issue_type="heading_order_warning",
                    page_url=page_url,
                    element="h1",
                    evidence="На странице не найден заголовок h1; требуется ручная проверка структуры.",
                    severity="low",
                ),
            ) or truncated

        previous_level: int | None = None
        for heading in headings:
            level = int(heading.name[1])
            if previous_level is not None and level > previous_level + 1:
                counts["heading_order_warnings_count"] += 1
                truncated = self._add_issue(
                    items,
                    self._issue(
                        "heading_order_warning",
                        page_url,
                        heading,
                        f"h{previous_level} -> h{level}",
                        "low",
                    ),
                ) or truncated
            previous_level = level
        return truncated

    def _check_duplicate_ids(
        self,
        soup: BeautifulSoup,
        page_url: str,
        items: list[AccessibilityIssueItem],
        counts: dict[str, int],
    ) -> bool:
        id_values = [
            str(tag.get("id")).strip()
            for tag in soup.find_all(id=True)
            if isinstance(tag, Tag) and str(tag.get("id")).strip()
        ]
        duplicates = sorted(value for value, count in Counter(id_values).items() if count > 1)
        truncated = False
        for value in duplicates:
            counts["duplicate_ids_count"] += 1
            truncated = self._add_issue(
                items,
                AccessibilityIssueItem(
                    issue_type="duplicate_id",
                    page_url=page_url,
                    element="[id]",
                    evidence=self._limit_evidence(value),
                    severity="low",
                ),
            ) or truncated
        return truncated

    def _has_field_label(self, field: Tag, soup: BeautifulSoup) -> bool:
        if self._accessible_text(field):
            return True
        if str(field.get("placeholder", "")).strip():
            return True
        field_id = field.get("id")
        if isinstance(field_id, str) and field_id.strip():
            label = soup.find("label", attrs={"for": field_id})
            if isinstance(label, Tag) and label.get_text(" ", strip=True):
                return True
        return field.find_parent("label") is not None

    def _accessible_text(self, tag: Tag) -> str:
        text = tag.get_text(" ", strip=True)
        if text:
            return text
        for attr_name in ("aria-label", "title", "aria-labelledby"):
            value = tag.get(attr_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _input_type(self, tag: Tag) -> str:
        value = tag.get("type")
        return str(value).strip().lower() if value else "text"

    def _issue(
        self,
        issue_type: str,
        page_url: str,
        tag: Tag,
        evidence: str,
        severity: str,
    ) -> AccessibilityIssueItem:
        return AccessibilityIssueItem(
            issue_type=issue_type,
            page_url=page_url,
            element=tag.name or "unknown",
            evidence=self._limit_evidence(evidence),
            severity=severity,
        )

    def _add_issue(
        self,
        items: list[AccessibilityIssueItem],
        issue: AccessibilityIssueItem,
    ) -> bool:
        if len(items) >= self.max_items:
            return True
        items.append(issue)
        return False

    def _attr_or_element(self, tag: Tag, attr_name: str) -> str:
        value = tag.get(attr_name)
        if isinstance(value, str) and value.strip():
            return self._normalize_attr_evidence(value)
        return self._element_html(tag)

    def _normalize_attr_evidence(self, value: str) -> str:
        normalized = value.strip()
        if normalized.lower().startswith("data:image"):
            return "inline data image"
        return normalized

    def _element_html(self, tag: Tag) -> str:
        return str(tag)

    def _limit_evidence(self, value: str) -> str:
        normalized = " ".join(str(value).split())
        return normalized[: self.evidence_limit]

    def _warnings(self, issues_found: bool, truncated: bool) -> list[str]:
        warnings: list[str] = []
        if issues_found:
            warnings.append(
                "Обнаружены признаки возможных проблем доступности; требуется ручная проверка."
            )
        if truncated:
            warnings.append("Список замечаний ограничен первыми 100 элементами.")
        return warnings
