from urllib.parse import urljoin, urlsplit

from app.schemas.forms import FormsResult
from app.schemas.pages import PageData
from app.schemas.security import InsecureFormAction, SecurityResult


class HttpsAnalyzer:
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

        return SecurityResult(
            https_enabled=https_enabled,
            has_mixed_content=None,
            insecure_form_actions=insecure_actions,
        )

    def _is_insecure_action(self, page_url: str, action: str | None) -> bool:
        if not action:
            return False

        absolute_action = urljoin(page_url, action)
        return urlsplit(absolute_action).scheme == "http"
