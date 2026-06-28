from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.pages import PageData
from app.schemas.policy import PolicyCandidate, PolicyMatchedLink, PolicyResult


class PolicyAnalyzer:
    key_phrases = (
        "политика обработки персональных данных",
        "политика конфиденциальности",
        "персональные данные",
        "privacy policy",
        "конфиденциальность",
        "условия конфиденциальности",
        "конфиденциальность персональной информации",
        "персональная информация",
        "обработка персональной информации",
        "cookies",
    )
    strong_document_phrases = (
        "условия конфиденциальности",
        "конфиденциальность персональной информации",
        "обработка персональной информации",
    )
    document_phrases = (
        "персональная информация",
        "персональные данные",
        "cookies",
    )
    url_markers = ("privacy", "policy", "personal-data", "confidentiality")

    def analyze(self, pages: list[PageData]) -> PolicyResult:
        matched_links: list[PolicyMatchedLink] = []
        candidates: list[PolicyCandidate] = []
        seen_matches: set[tuple[str, str]] = set()
        seen_candidates: set[tuple[str, str]] = set()

        for page in pages:
            if not page.html:
                continue

            soup = BeautifulSoup(page.html, "html.parser")
            base_url = page.final_url or page.url
            page_is_candidate = self._looks_like_policy_url(base_url)
            if page_is_candidate:
                self._append_candidate(
                    candidates,
                    seen_candidates,
                    page_url=base_url,
                    url=base_url,
                    reason="scanned_page_url",
                )

            if (
                page_is_candidate or self._has_policy_heading(soup)
            ) and self._looks_like_policy_document(soup):
                self._append_match(
                    matched_links,
                    seen_matches,
                    page_url=base_url,
                    href=base_url,
                    text=self._document_title(soup),
                )

            for anchor in soup.find_all("a", href=True):
                if not isinstance(anchor, Tag):
                    continue

                text = anchor.get_text(" ", strip=True)
                href = self._get_href(anchor, base_url)
                haystack = f"{text} {href}".lower()
                if any(phrase in haystack for phrase in self.key_phrases):
                    self._append_match(
                        matched_links,
                        seen_matches,
                        page_url=base_url,
                        href=href,
                        text=text or None,
                    )
                elif self._looks_like_policy_url(href):
                    self._append_candidate(
                        candidates,
                        seen_candidates,
                        page_url=base_url,
                        url=href,
                        reason="link_url",
                    )

        return PolicyResult(
            found=bool(matched_links),
            matched_links=matched_links,
            candidates=candidates,
            policy_url=matched_links[0].href if matched_links else None,
        )

    def _get_href(self, anchor: Tag, base_url: str) -> str:
        raw_href = anchor.get("href")
        href = raw_href.strip() if isinstance(raw_href, str) else ""
        return urljoin(base_url, href)

    def _looks_like_policy_url(self, url: str) -> bool:
        parsed = urlsplit(url)
        haystack = f"{parsed.path} {parsed.query}".lower()
        return any(marker in haystack for marker in self.url_markers)

    def _looks_like_policy_document(self, soup: BeautifulSoup) -> bool:
        text = soup.get_text(" ", strip=True).lower()
        if any(phrase in text for phrase in self.strong_document_phrases):
            return True

        matched_phrases = {
            phrase for phrase in self.document_phrases if phrase in text
        }
        return len(matched_phrases) >= 2

    def _has_policy_heading(self, soup: BeautifulSoup) -> bool:
        heading = soup.find(["h1", "title"])
        if not isinstance(heading, Tag):
            return False

        text = heading.get_text(" ", strip=True).lower()
        return any(phrase in text for phrase in self.key_phrases)

    def _document_title(self, soup: BeautifulSoup) -> str | None:
        heading = soup.find(["h1", "title"])
        if not isinstance(heading, Tag):
            return None

        text = heading.get_text(" ", strip=True)
        return text or None

    def _append_match(
        self,
        matched_links: list[PolicyMatchedLink],
        seen: set[tuple[str, str]],
        page_url: str,
        href: str,
        text: str | None,
    ) -> None:
        key = (page_url, href)
        if key in seen:
            return

        seen.add(key)
        matched_links.append(PolicyMatchedLink(page_url=page_url, href=href, text=text))

    def _append_candidate(
        self,
        candidates: list[PolicyCandidate],
        seen: set[tuple[str, str]],
        page_url: str,
        url: str,
        reason: str,
    ) -> None:
        key = (page_url, url)
        if key in seen:
            return

        seen.add(key)
        candidates.append(PolicyCandidate(page_url=page_url, url=url, reason=reason))
