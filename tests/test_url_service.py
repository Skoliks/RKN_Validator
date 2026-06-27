import pytest

from app.core.exceptions import InvalidUrlError, InvalidUserInputError
from app.services.url_service import UrlService


def test_normalizes_plain_domain() -> None:
    result = UrlService().normalize("example.ru")

    assert result.normalized_url == "https://example.ru"
    assert result.final_url == "https://example.ru"
    assert result.domain == "example.ru"
    assert result.domain_zone == "ru"


def test_normalizes_www_domain() -> None:
    result = UrlService().normalize("www.example.ru")

    assert result.normalized_url == "https://www.example.ru"
    assert result.domain == "www.example.ru"
    assert result.domain_zone == "ru"


def test_removes_root_trailing_slash() -> None:
    result = UrlService().normalize("https://example.ru/")

    assert result.normalized_url == "https://example.ru"
    assert result.final_url == "https://example.ru"


def test_normalizes_company_io() -> None:
    result = UrlService().normalize("company.io")

    assert result.normalized_url == "https://company.io"
    assert result.domain == "company.io"
    assert result.domain_zone == "io"


def test_rejects_plain_text() -> None:
    with pytest.raises(InvalidUserInputError) as exc_info:
        UrlService().normalize("какая сегодня погода")

    assert str(exc_info.value) == (
        "Не понял ваш запрос, пожалуйста отправьте ссылку на сайт для проверки."
    )
    assert exc_info.value.code == "not_a_url"


def test_rejects_scheme_without_host() -> None:
    with pytest.raises(InvalidUrlError) as exc_info:
        UrlService().normalize("https://")

    assert str(exc_info.value) == (
        "Ссылка указана некорректно, пожалуйста отправьте адрес сайта "
        "в формате https://example.ru."
    )
    assert exc_info.value.code == "invalid_url"


def test_rejects_empty_string() -> None:
    with pytest.raises(InvalidUserInputError):
        UrlService().normalize("")


def test_rejects_whitespace_only_string() -> None:
    with pytest.raises(InvalidUserInputError):
        UrlService().normalize("   ")
