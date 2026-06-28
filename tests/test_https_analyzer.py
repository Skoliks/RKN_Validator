from app.analyzers.form_analyzer import FormAnalyzer
from app.analyzers.https_analyzer import HttpsAnalyzer
from app.schemas.pages import PageData


def make_page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def test_https_analyzer_detects_http_form_action() -> None:
    page = make_page('<form action="http://example.ru/send"><input name="phone" /></form>')
    forms = FormAnalyzer().analyze([page])

    result = HttpsAnalyzer().analyze([page], forms)

    assert result.https_enabled is True
    assert len(result.insecure_form_actions) == 1
    assert result.insecure_form_actions[0].action == "http://example.ru/send"


def test_https_analyzer_detects_yastatic_http_mixed_content_on_https_page() -> None:
    page = make_page(
        '<script src="http://yastatic.net/jquery/3.7.1/jquery.min.js"></script>',
        url="https://example.ru",
    )
    forms = FormAnalyzer().analyze([page])

    result = HttpsAnalyzer().analyze([page], forms)

    assert result.has_mixed_content is True
    assert len(result.mixed_content_items) == 1
    assert result.mixed_content_items[0].url == "http://yastatic.net/jquery/3.7.1/jquery.min.js"
