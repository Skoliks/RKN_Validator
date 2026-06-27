from app.analyzers.policy_analyzer import PolicyAnalyzer
from app.schemas.pages import PageData


def make_page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def test_policy_analyzer_detects_policy_link() -> None:
    html = '<a href="/privacy">Политика обработки персональных данных</a>'

    result = PolicyAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.policy_url == "https://example.ru/privacy"
    assert result.matched_links[0].text == "Политика обработки персональных данных"


def test_policy_analyzer_returns_empty_result_without_policy() -> None:
    result = PolicyAnalyzer().analyze([make_page('<a href="/about">О компании</a>')])

    assert result.found is False
    assert result.policy_url is None
    assert result.matched_links == []


def test_policy_analyzer_handles_invalid_html() -> None:
    html = '<a href="/privacy">privacy policy'

    result = PolicyAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.policy_url == "https://example.ru/privacy"
