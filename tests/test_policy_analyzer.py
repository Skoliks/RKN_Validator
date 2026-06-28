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


def test_policy_analyzer_detects_waba_privacy_ru_candidate_by_page_url() -> None:
    page = make_page(
        "<html><body>Document page</body></html>",
        url="https://infocom.io/waba-privacy-ru",
    )

    result = PolicyAnalyzer().analyze([page])

    assert result.found is False
    assert result.policy_url is None
    assert len(result.candidates) == 1
    assert result.candidates[0].url == "https://infocom.io/waba-privacy-ru"


def test_policy_analyzer_detects_waba_privacy_ru_document() -> None:
    footer_page = make_page(
        '<footer><a href="/waba-privacy-ru">Условия конфиденциальности</a></footer>',
        url="https://infocom.io",
    )
    policy_page = make_page(
        """
        <html>
          <h1>Условия о конфиденциальности персональной информации</h1>
          <p>Оператор выполняет обработку персональной информации пользователей.</p>
          <p>Cookies используются для целей обработки и улучшения сервиса.</p>
          <p>Контактные данные оператора размещены в настоящем документе.</p>
        </html>
        """,
        url="https://infocom.io/waba-privacy-ru",
    )

    result = PolicyAnalyzer().analyze([footer_page, policy_page])

    assert result.found is True
    assert result.policy_url == "https://infocom.io/waba-privacy-ru"
    assert result.matched_links[0].href == "https://infocom.io/waba-privacy-ru"
    assert result.matched_links[0].text == "Условия конфиденциальности"
    assert result.matched_links[0].page_url == "https://infocom.io"
