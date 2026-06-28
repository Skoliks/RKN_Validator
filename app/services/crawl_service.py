from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.core.config import settings
from app.infrastructure.http_client import HttpClient, HttpResponse
from app.schemas.pages import CrawlResult, PageData, WarningItem
from app.schemas.site import SiteInfo


class CrawlService:
    priority_markers = (
        "privacy",
        "policy",
        "personal-data",
        "contacts",
        "contact",
        "about",
        "login",
        "register",
    )

    def __init__(self, http_client: HttpClient | None = None, max_pages: int | None = None) -> None:
        self.http_client = http_client or HttpClient()
        self.max_pages = max_pages if max_pages is not None else settings.max_pages_per_site

    async def crawl(self, site: SiteInfo) -> CrawlResult:
        pages: list[PageData] = []
        warnings: list[WarningItem] = []

        try:
            main_response = await self.http_client.get(site.normalized_url)
        except Exception as exc:
            return CrawlResult(
                pages=pages,
                warnings=[
                    WarningItem(
                        code="main_page_unavailable",
                        message=f"Главную страницу не удалось загрузить: {type(exc).__name__}.",
                    )
                ],
            )

        pages.append(self._to_page_data(site.normalized_url, main_response))

        selected_links = self._select_links(
            html=main_response.html,
            base_url=main_response.final_url,
            source_domain=site.domain,
            limit=max(self.max_pages - 1, 0),
        )

        for link in selected_links:
            try:
                response = await self.http_client.get(link)
            except Exception as exc:
                warnings.append(
                    WarningItem(
                        code="page_unavailable",
                        message=f"Страницу не удалось загрузить: {type(exc).__name__}.",
                    )
                )
                continue

            pages.append(self._to_page_data(link, response))

            if len(pages) >= self.max_pages:
                break

        return CrawlResult(pages=pages, warnings=warnings)

    def _to_page_data(self, requested_url: str, response: HttpResponse) -> PageData:
        return PageData(
            url=requested_url,
            final_url=response.final_url,
            status_code=response.status_code,
            html=response.html,
        )

    def _select_links(
        self,
        html: str,
        base_url: str,
        source_domain: str,
        limit: int,
    ) -> list[str]:
        if limit <= 0:
            return []

        links = self._extract_internal_links(html, base_url, source_domain)
        prioritized = sorted(
            enumerate(links),
            key=lambda item: (self._priority_rank(item[1]), item[0]),
        )
        return [link for _, link in prioritized[:limit]]

    def _extract_internal_links(
        self,
        html: str,
        base_url: str,
        source_domain: str,
    ) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            normalized_link = self._normalize_link(
                href=anchor["href"],
                base_url=base_url,
                source_domain=source_domain,
            )
            if normalized_link is None or normalized_link in seen:
                continue

            seen.add(normalized_link)
            links.append(normalized_link)

        return links

    def _normalize_link(
        self,
        href: str,
        base_url: str,
        source_domain: str,
    ) -> str | None:
        absolute_url = urljoin(base_url, href.strip())
        parsed = urlsplit(absolute_url)

        if parsed.scheme not in {"http", "https"}:
            return None

        hostname = parsed.hostname
        if hostname is None or hostname.lower().rstrip(".") != source_domain:
            return None

        path = "" if parsed.path == "/" else parsed.path
        return urlunsplit((parsed.scheme, parsed.netloc.lower(), path, parsed.query, ""))

    def _priority_rank(self, url: str) -> int:
        lowered_url = url.lower()
        for index, marker in enumerate(self.priority_markers):
            if marker in lowered_url:
                return index
        return len(self.priority_markers)
