import re

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.forms import FormField, FormItem, FormsResult
from app.schemas.pages import PageData


class FormAnalyzer:
    field_markers = {
        "message": ("message", "comment", "msg", "сообщение", "комментарий"),
        "name": ("name", "fio", "fullname", "first_name", "last_name", "имя", "фио"),
        "phone": ("phone", "tel", "mobile", "телефон", "номер"),
        "email": ("email", "mail", "e-mail", "почта"),
        "address": ("address", "addr", "адрес"),
        "company": ("company", "organization", "org", "компания", "организация"),
        "inn": ("inn", "инн"),
    }
    fallback_field_pattern = re.compile(r"<(input|textarea|select|button)\b([^>]*)", re.IGNORECASE)
    fallback_attr_pattern = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*['\"]([^'\"]*)['\"]")

    def analyze(self, pages: list[PageData]) -> FormsResult:
        items: list[FormItem] = []

        for page in pages:
            if not page.html:
                continue

            soup = BeautifulSoup(page.html, "html.parser")
            for form in soup.find_all("form"):
                if not isinstance(form, Tag):
                    continue

                fields = [
                    self._build_field(field, soup)
                    for field in form.find_all(["input", "textarea", "select", "button"])
                    if isinstance(field, Tag)
                ]
                fields.extend(self._extract_fallback_fields(str(form), fields))
                if not fields:
                    fields.extend(self._extract_fallback_fields(page.html, fields))
                items.append(
                    FormItem(
                        page_url=page.final_url or page.url,
                        action=self._get_attr(form, "action"),
                        method=(self._get_attr(form, "method") or "get").lower(),
                        fields=fields,
                    )
                )

        return FormsResult(found=bool(items), total=len(items), items=items)

    def _extract_fallback_fields(self, html: str, existing_fields: list[FormField]) -> list[FormField]:
        existing_names = {field.name for field in existing_fields if field.name}
        fields: list[FormField] = []

        for match in self.fallback_field_pattern.finditer(html):
            tag_name = match.group(1).lower()
            attrs = {
                attr_match.group(1).lower(): attr_match.group(2).strip()
                for attr_match in self.fallback_attr_pattern.finditer(match.group(2))
            }
            name = attrs.get("name") or attrs.get("id")
            if name in existing_names:
                continue

            input_type = attrs.get("type") or tag_name
            marker_text = " ".join(
                value
                for value in (
                    name,
                    input_type,
                    attrs.get("placeholder"),
                )
                if value
            )
            fields.append(
                FormField(
                    name=name,
                    field_type=self._classify_field(marker_text, input_type),
                    required="required" in attrs,
                    label=None,
                )
            )

        return fields

    def _build_field(self, field: Tag, soup: BeautifulSoup) -> FormField:
        name = self._get_attr(field, "name") or self._get_attr(field, "id")
        input_type = self._get_attr(field, "type") or field.name
        label = self._find_label(field, soup)
        marker_text = " ".join(
            value
            for value in (
                name,
                input_type,
                self._get_attr(field, "placeholder"),
                label,
                self._nearest_text(field),
            )
            if value
        )

        return FormField(
            name=name,
            field_type=self._classify_field(marker_text, input_type),
            required=field.has_attr("required"),
            label=label,
        )

    def _classify_field(self, marker_text: str, input_type: str | None) -> str:
        lowered_text = marker_text.lower()
        lowered_type = (input_type or "").lower()

        if lowered_type == "email":
            return "email"
        if lowered_type == "tel":
            return "phone"

        for field_type, markers in self.field_markers.items():
            if any(marker in lowered_text for marker in markers):
                return field_type

        return "unknown"

    def _find_label(self, field: Tag, soup: BeautifulSoup) -> str | None:
        field_id = self._get_attr(field, "id")
        if field_id:
            label = soup.find("label", attrs={"for": field_id})
            if isinstance(label, Tag):
                return label.get_text(" ", strip=True) or None

        parent_label = field.find_parent("label")
        if isinstance(parent_label, Tag):
            return parent_label.get_text(" ", strip=True) or None

        return None

    def _nearest_text(self, field: Tag) -> str | None:
        parent = field.parent
        if isinstance(parent, Tag):
            return parent.get_text(" ", strip=True)[:200] or None
        return None

    def _get_attr(self, tag: Tag, attr_name: str) -> str | None:
        value = tag.get(attr_name)
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return None
