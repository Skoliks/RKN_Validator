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
