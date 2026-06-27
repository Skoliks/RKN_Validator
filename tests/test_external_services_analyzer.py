from app.analyzers.external_services_analyzer import ExternalServicesAnalyzer
from app.schemas.pages import PageData


def make_page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def test_external_services_analyzer_detects_google_tag_manager() -> None:
    html = '<script src="https://www.googletagmanager.com/gtm.js?id=GTM-123"></script>'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].provider == "Google Tag Manager"
    assert result.items[0].service_type == "analytics"


def test_external_services_analyzer_detects_yandex_metrika() -> None:
    html = '<img src="https://mc.yandex.ru/watch/12345" />'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].provider == "Yandex Metrika"
    assert result.items[0].service_type == "analytics"


def test_external_services_analyzer_detects_external_link() -> None:
    html = '<a href="https://partner.example.com/page">Partner</a>'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].provider is None
    assert result.items[0].service_type == "external_link"
    assert result.items[0].url == "https://partner.example.com/page"


def test_external_services_analyzer_ignores_internal_links() -> None:
    html = """
    <a href="/privacy">Privacy</a>
    <script src="https://example.ru/static/app.js"></script>
    <form action="/send"></form>
    """

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is False
    assert result.items == []


def test_external_services_analyzer_handles_invalid_html() -> None:
    html = '<script src="https://www.googletagmanager.com/gtm.js"'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].provider == "Google Tag Manager"
