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
    assert result.items[0].foreign is False


def test_external_services_analyzer_classifies_yastatic_as_non_foreign_cdn() -> None:
    html = '<script src="https://yastatic.net/jquery/3.7.1/jquery.min.js"></script>'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].provider == "Yandex"
    assert result.items[0].service_type == "cdn"
    assert result.items[0].foreign is False


def test_external_services_analyzer_classifies_unpkg_as_foreign_cdn() -> None:
    html = '<script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].provider == "UNPKG"
    assert result.items[0].service_type == "cdn"
    assert result.items[0].foreign is True


def test_external_services_analyzer_classifies_social_network_link() -> None:
    html = '<a href="https://facebook.com/company">Facebook</a>'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].provider == "Facebook"
    assert result.items[0].service_type == "social_network"


def test_external_services_analyzer_classifies_bitrix24_widget() -> None:
    html = '<script src="https://example.bitrix24.net/widget/script.js"></script>'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].provider == "Bitrix24"
    assert result.items[0].service_type == "crm_widget"
    assert result.items[0].foreign is False


def test_external_services_analyzer_detects_external_link() -> None:
    html = '<a href="https://partner.example.com/page">Partner</a>'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].provider is None
    assert result.items[0].service_type == "external_link"
    assert result.items[0].url == "https://partner.example.com/page"


def test_external_services_analyzer_normalizes_ampersand_and_deduplicates_urls() -> None:
    html = """
    <script src="https://cdn.example.com/widget.js?a=1&amp;b=2"></script>
    <script src="https://cdn.example.com/widget.js?a=1&b=2"></script>
    """

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert len(result.items) == 1
    assert result.items[0].url == "https://cdn.example.com/widget.js?a=1&b=2"


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


def test_external_services_analyzer_skips_invalid_urls_without_crashing() -> None:
    html = '<a href="[bad:url">bad</a><img src="http://[bad">'

    result = ExternalServicesAnalyzer().analyze([make_page(html)])

    assert result.found is False
    assert result.items == []


def test_external_services_analyzer_splits_external_link_and_resource() -> None:
    html = """
    <a href="https://iana.org/domains/example">IANA</a>
    <script src="https://cdn.example.net/app.js"></script>
    """

    result = ExternalServicesAnalyzer().analyze([make_page(html, url="https://example.com")])

    assert {item.service_type for item in result.items} == {
        "external_link",
        "external_resource",
    }
