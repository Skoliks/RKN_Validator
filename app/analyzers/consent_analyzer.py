from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.consents import ConsentItem, ConsentsResult
from app.schemas.forms import FormItem, FormsResult
from app.schemas.pages import PageData


class ConsentAnalyzer:
    consent_phrases = (
        "согласие на обработку персональных данных",
        "персональные данные",
        "политика обработки персональных данных",
        "политика конфиденциальности",
        "нажимая кнопку",
        "соглашаюсь",
    )

    def analyze(self, pages: list[PageData], forms: FormsResult) -> ConsentsResult:
        items: list[ConsentItem] = []
        forms_by_page = self._group_forms_by_page(forms.items)

        for page in pages:
            if not page.html:
                continue

            page_url = page.final_url or page.url
            page_forms = forms_by_page.get(page_url, [])
            if not page_forms:
                continue

            soup = BeautifulSoup(page.html, "html.parser")
            form_tags = [form for form in soup.find_all("form") if isinstance(form, Tag)]

            for index, form_item in enumerate(page_forms):
                form_tag = form_tags[index] if index < len(form_tags) else None
                text = self._get_near_form_text(form_tag, soup)
                matched_text = self._find_consent_text(text)
                if matched_text is None:
                    continue

                items.append(
                    ConsentItem(
                        page_url=page_url,
                        form_id=form_item.form_id,
                        consent_type="personal_data",
                        text=matched_text,
                        selector="form",
                    )
                )

        return ConsentsResult(found=bool(items), items=items)

    def _group_forms_by_page(self, forms: list[FormItem]) -> dict[str, list[FormItem]]:
        grouped: dict[str, list[FormItem]] = {}
        for form in forms:
            grouped.setdefault(form.page_url, []).append(form)
        return grouped

    def _get_near_form_text(self, form: Tag | None, soup: BeautifulSoup) -> str:
        if form is None:
            return soup.get_text(" ", strip=True)

        parts = [form.get_text(" ", strip=True)]
        next_node = form.find_next_sibling()
        previous_node = form.find_previous_sibling()

        if isinstance(next_node, Tag):
            parts.append(next_node.get_text(" ", strip=True))
        if isinstance(previous_node, Tag):
            parts.append(previous_node.get_text(" ", strip=True))

        return " ".join(part for part in parts if part)

    def _find_consent_text(self, text: str) -> str | None:
        lowered_text = text.lower()
        for phrase in self.consent_phrases:
            if phrase in lowered_text:
                return text[:500]
        return None
