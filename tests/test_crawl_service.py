import pytest

from app.services.crawl_service import CrawlService
from app.schemas.site import SiteInfo


def make_site() -> SiteInfo:
    return SiteInfo(
        original_input="example.ru",
        normalized_url="https://example.ru",
        final_url="https://example.ru",
        domain="example.ru",
        domain_zone="ru",
    )


@pytest.mark.asyncio
async def test_crawl_extracts_internal_links_and_prioritizes_pages(httpx_mock) -> None:
    html = """
    <html>
      <body>
        <a href="/random">Random</a>
        <a href="/privacy">Privacy</a>
        <a href="/contacts">Contacts</a>
        <a href="https://external.test/policy">External</a>
      </body>
    </html>
    """
    httpx_mock.add_response(url="https://example.ru", text=html)
    httpx_mock.add_response(url="https://example.ru/privacy", text="<html>privacy</html>")
    httpx_mock.add_response(url="https://example.ru/contacts", text="<html>contacts</html>")
    httpx_mock.add_response(url="https://example.ru/random", text="<html>random</html>")

    result = await CrawlService().crawl(make_site())

    urls = [page.url for page in result.pages]
    assert urls == [
        "https://example.ru",
        "https://example.ru/privacy",
        "https://example.ru/contacts",
        "https://example.ru/random",
    ]
    assert result.pages[0].html == html


@pytest.mark.asyncio
async def test_crawl_does_not_leave_source_domain(httpx_mock) -> None:
    html = """
    <html>
      <body>
        <a href="/privacy">Privacy</a>
        <a href="https://example.com/privacy">External domain</a>
        <a href="https://sub.example.ru/login">Subdomain</a>
      </body>
    </html>
    """
    httpx_mock.add_response(url="https://example.ru", text=html)
    httpx_mock.add_response(url="https://example.ru/privacy", text="<html>privacy</html>")

    result = await CrawlService().crawl(make_site())

    assert [page.url for page in result.pages] == [
        "https://example.ru",
        "https://example.ru/privacy",
    ]


@pytest.mark.asyncio
async def test_crawl_limits_pages(httpx_mock) -> None:
    html = """
    <html>
      <body>
        <a href="/privacy">Privacy</a>
        <a href="/policy">Policy</a>
        <a href="/personal-data">Personal data</a>
        <a href="/contacts">Contacts</a>
        <a href="/about">About</a>
        <a href="/login">Login</a>
      </body>
    </html>
    """
    httpx_mock.add_response(url="https://example.ru", text=html)
    httpx_mock.add_response(url="https://example.ru/privacy", text="<html>privacy</html>")
    httpx_mock.add_response(url="https://example.ru/policy", text="<html>policy</html>")
    httpx_mock.add_response(url="https://example.ru/personal-data", text="<html>personal-data</html>")
    httpx_mock.add_response(url="https://example.ru/contacts", text="<html>contacts</html>")

    result = await CrawlService(max_pages=5).crawl(make_site())

    assert len(result.pages) == 5
    assert [page.url for page in result.pages] == [
        "https://example.ru",
        "https://example.ru/privacy",
        "https://example.ru/policy",
        "https://example.ru/personal-data",
        "https://example.ru/contacts",
    ]
