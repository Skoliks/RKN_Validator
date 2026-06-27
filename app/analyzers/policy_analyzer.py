from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.pages import PageData
from app.schemas.policy import PolicyMatchedLink, PolicyResult


class PolicyAnalyzer:
    key_phrases = (
        "политика обработки персональных данных",
        "политика конфиденциальности",
        "персональные данные",
        "privacy policy",
        "конфиденциальность",
    )

    def analyze(self, pages: list[PageData]) -> PolicyResult:
        matched_links: list[PolicyMatchedLink] = []

        for page in pages:
            if not page.html:
                continue

            soup = BeautifulSoup(page.html, "html.parser")
            base_url = page.final_url or page.url

            for anchor in soup.find_all("a", href=True):
                if not isinstance(anchor, Tag):
                    continue

                text = anchor.get_text(" ", strip=True)
                href = self._get_href(anchor, base_url)
                haystack = f"{text} {href}".lower()
                if any(phrase in haystack for phrase in self.key_phrases):
                    matched_links.append(
                        PolicyMatchedLink(
                            page_url=base_url,
                            href=href,
                            text=text or None,
                        )
                    )

        return PolicyResult(
            found=bool(matched_links),
            matched_links=matched_links,
            policy_url=matched_links[0].href if matched_links else None,
        )

    def _get_href(self, anchor: Tag, base_url: str) -> str:
        raw_href = anchor.get("href")
        href = raw_href.strip() if isinstance(raw_href, str) else ""
        return urljoin(base_url, href)
