from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.forms import FormsResult
from app.schemas.pages import PageData
from app.schemas.security import InsecureFormAction, MixedContentItem, SecurityResult


class HttpsAnalyzer:
    resource_selectors = (
        ("script", "src"),
        ("link", "href"),
        ("img", "src"),
        ("iframe", "src"),
        ("source", "src"),
        ("video", "src"),
        ("audio", "src"),
    )

    def analyze(self, pages: list[PageData], forms: FormsResult) -> SecurityResult:
        page_urls = [page.final_url or page.url for page in pages]
        https_enabled = all(urlsplit(url).scheme == "https" for url in page_urls) if page_urls else None

        insecure_actions = [
            InsecureFormAction(
                page_url=form.page_url,
                action=form.action,
                reason="Form action uses insecure HTTP.",
            )
            for form in forms.items
            if self._is_insecure_action(form.page_url, form.action)
        ]
        mixed_content_items = self._find_mixed_content(pages)

        return SecurityResult(
            https_enabled=https_enabled,
            has_mixed_content=bool(mixed_content_items),
            mixed_content_items=mixed_content_items,
            insecure_form_actions=insecure_actions,
        )

    def _is_insecure_action(self, page_url: str, action: str | None) -> bool:
        if not action:
            return False

        absolute_action = urljoin(page_url, action)
        return urlsplit(absolute_action).scheme == "http"

    def _find_mixed_content(self, pages: list[PageData]) -> list[MixedContentItem]:
        items: list[MixedContentItem] = []
        seen: set[tuple[str, str, str, str]] = set()

        for page in pages:
            if not page.html:
                continue

            page_url = page.final_url or page.url
            if urlsplit(page_url).scheme != "https":
                continue

            soup = BeautifulSoup(page.html, "html.parser")
            for tag_name, attr_name in self.resource_selectors:
                for tag in soup.find_all(tag_name):
                    if not isinstance(tag, Tag):
                        continue

                    value = tag.get(attr_name)
                    if not isinstance(value, str):
                        continue

                    url = urljoin(page_url, value.strip())
                    if urlsplit(url).scheme != "http":
                        continue

                    key = (page_url, url, tag_name, attr_name)
                    if key in seen:
                        continue

                    seen.add(key)
                    items.append(
                        MixedContentItem(
                            page_url=page_url,
                            url=url,
                            tag=tag_name,
                            attribute=attr_name,
                        )
                    )

        return items
