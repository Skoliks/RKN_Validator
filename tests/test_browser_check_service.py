import builtins

import pytest

from app.infrastructure.browser_client import BrowserClient
from app.schemas.browser import (
    BrowserCheckResult,
    BrowserCookieItem,
    CookieInteractionResult,
    BrowserNetworkRequest,
    BrowserPageResult,
)
from app.services.browser_check_service import BrowserCheckService


class FakeRequest:
    method = "GET"
    resource_type = "script"


class FakeResponse:
    def __init__(self, url: str, status: int = 200) -> None:
        self.url = url
        self.status = status
        self.request = FakeRequest()


class FakeBrowserClient:
    async def check_page(self, url: str, source_domain: str | None = None) -> BrowserPageResult:
        return BrowserPageResult(
            browser_check_performed=True,
            url=url,
            final_url=url,
            title="Example",
            cookies_after_load=[
                BrowserCookieItem(
                    name="session",
                    domain="example.ru",
                    path="/",
                    http_only=True,
                    secure=True,
                    same_site="Lax",
                )
            ],
            network_requests=[
                BrowserNetworkRequest(
                    url=f"https://cdn{i}.example.net/script.js",
                    method="GET",
                    resource_type="script",
                    status_code=200,
                    domain=f"cdn{i}.example.net",
                    is_third_party=True,
                )
                for i in range(3)
            ],
        )

    async def check_cookie_interaction(
        self,
        url: str,
        source_domain: str | None = None,
    ) -> CookieInteractionResult:
        return CookieInteractionResult(
            enabled=True,
            performed=True,
            banner_found=False,
            reject_clicked=False,
            accept_clicked=False,
        )


class TimeoutCookieInteractionClient(FakeBrowserClient):
    async def check_cookie_interaction(
        self,
        url: str,
        source_domain: str | None = None,
    ) -> CookieInteractionResult:
        raise TimeoutError()


@pytest.mark.asyncio
async def test_browser_check_service_returns_disabled_result_when_off() -> None:
    result = await BrowserCheckService(
        browser_client=FakeBrowserClient(),
        enabled=False,
    ).check(["https://example.ru"], source_domain="example.ru")

    assert result.enabled is False
    assert result.performed is False
    assert result.pages_checked == 0
    assert result.items == []


@pytest.mark.asyncio
async def test_browser_client_handles_missing_playwright(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError("No module named playwright")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = await BrowserClient().check_page("https://example.ru", source_domain="example.ru")

    assert result.browser_check_performed is False
    assert result.error_type == "browser_not_installed"
    assert "Playwright is not installed" in (result.message or "")


def test_browser_models_validate() -> None:
    page = BrowserPageResult(
        browser_check_performed=True,
        url="https://example.ru",
        final_url="https://example.ru/",
        title="Example",
        cookies_after_load=[BrowserCookieItem(name="cookie")],
        network_requests=[
            BrowserNetworkRequest(
                url="https://example.ru/app.js",
                is_third_party=False,
            )
        ],
    )
    result = BrowserCheckResult(enabled=True, performed=True, pages_checked=1, items=[page])

    assert result.items[0].cookies_after_load[0].name == "cookie"
    assert result.items[0].network_requests[0].is_third_party is False


def test_browser_client_normalizes_network_url_without_query() -> None:
    requests: list[BrowserNetworkRequest] = []
    client = BrowserClient()

    client._capture_response(
        response=FakeResponse("https://mc.yandex.ru/watch/95830144?x=long&y=value"),
        source_domain="example.ru",
        network_requests=requests,
    )

    item = requests[0]
    assert item.url == "https://mc.yandex.ru/watch/95830144"
    assert item.path == "/watch/95830144"
    assert item.has_query is True
    assert item.original_url_truncated is True
    assert item.domain == "mc.yandex.ru"
    assert item.method == "GET"
    assert item.resource_type == "script"
    assert item.status_code == 200
    assert item.is_third_party is True


def test_browser_client_does_not_store_very_long_original_url() -> None:
    requests: list[BrowserNetworkRequest] = []
    long_query = "x=" + ("a" * 2000)

    BrowserClient()._capture_response(
        response=FakeResponse(f"https://googlevideo.com/videoplayback?{long_query}"),
        source_domain="example.ru",
        network_requests=requests,
    )

    item = requests[0]
    assert item.url == "https://googlevideo.com/videoplayback"
    assert long_query not in item.model_dump_json()
    assert item.has_query is True
    assert item.original_url_truncated is True


@pytest.mark.asyncio
async def test_browser_check_service_returns_cookies_network_and_limits_requests() -> None:
    result = await BrowserCheckService(
        browser_client=FakeBrowserClient(),
        enabled=True,
        cookie_interaction_enabled=False,
        max_network_requests=2,
    ).check(["https://example.ru"], source_domain="example.ru")

    assert result.enabled is True
    assert result.performed is True
    assert result.pages_checked == 1
    assert result.items[0].cookies_after_load[0].name == "session"
    assert len(result.items[0].network_requests) == 2
    assert result.items[0].network_requests[0].is_third_party is True
    assert "Network request list was truncated" in result.items[0].warnings[0]


@pytest.mark.asyncio
async def test_browser_check_service_handles_cookie_interaction_timeout() -> None:
    result = await BrowserCheckService(
        browser_client=TimeoutCookieInteractionClient(),
        enabled=True,
        cookie_interaction_enabled=True,
    ).check(["https://example.ru"], source_domain="example.ru")

    interaction = result.cookie_interaction

    assert interaction is not None
    assert interaction.enabled is True
    assert interaction.performed is True
    assert interaction.banner_found is False
    assert interaction.buttons_found == []
    assert interaction.reject_clicked is False
    assert interaction.accept_clicked is False
    assert (
        "Cookie-баннер или кнопка отклонения не были найдены автоматически."
        in interaction.warnings
    )
    assert "Cookie interaction check failed: TimeoutError." in interaction.warnings
