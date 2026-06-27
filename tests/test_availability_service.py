import ssl

import httpx
import pytest

from app.services.availability_service import AvailabilityService, UNAVAILABLE_MESSAGE
from app.schemas.site import SiteInfo


def make_site(url: str = "https://example.ru") -> SiteInfo:
    return SiteInfo(
        original_input=url,
        normalized_url=url,
        final_url=url,
        domain="example.ru",
        domain_zone="ru",
    )


@pytest.mark.asyncio
async def test_availability_returns_available_for_success(httpx_mock) -> None:
    httpx_mock.add_response(url="https://example.ru", status_code=200, text="<html></html>")

    result = await AvailabilityService().check(make_site())

    assert result.available is True
    assert result.status_code == 200
    assert result.error_type is None


@pytest.mark.asyncio
async def test_availability_maps_timeout(httpx_mock) -> None:
    httpx_mock.add_exception(httpx.ReadTimeout("timeout"))

    result = await AvailabilityService().check(make_site())

    assert result.available is False
    assert result.error_type == "timeout"
    assert result.message == UNAVAILABLE_MESSAGE


@pytest.mark.asyncio
async def test_availability_maps_dns_error(httpx_mock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("getaddrinfo failed"))

    result = await AvailabilityService().check(make_site())

    assert result.available is False
    assert result.error_type == "dns_error"
    assert result.message == UNAVAILABLE_MESSAGE


@pytest.mark.asyncio
async def test_availability_maps_ssl_error(httpx_mock) -> None:
    request = httpx.Request("GET", "https://example.ru")
    ssl_error = ssl.SSLError("certificate verify failed")
    connect_error = httpx.ConnectError("SSL error", request=request)
    connect_error.__cause__ = ssl_error
    httpx_mock.add_exception(connect_error)

    result = await AvailabilityService().check(make_site())

    assert result.available is False
    assert result.error_type == "ssl_error"
    assert result.message == UNAVAILABLE_MESSAGE


@pytest.mark.asyncio
async def test_availability_maps_too_many_redirects(httpx_mock) -> None:
    request = httpx.Request("GET", "https://example.ru")
    httpx_mock.add_exception(httpx.TooManyRedirects("too many redirects", request=request))

    result = await AvailabilityService().check(make_site())

    assert result.available is False
    assert result.error_type == "too_many_redirects"
    assert result.message == UNAVAILABLE_MESSAGE


@pytest.mark.asyncio
async def test_availability_maps_bad_status_to_site_unavailable(httpx_mock) -> None:
    httpx_mock.add_response(url="https://example.ru", status_code=503, text="")

    result = await AvailabilityService().check(make_site())

    assert result.available is False
    assert result.status_code == 503
    assert result.error_type == "site_unavailable"
    assert result.message == UNAVAILABLE_MESSAGE
