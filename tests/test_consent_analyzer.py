from app.analyzers.consent_analyzer import ConsentAnalyzer
from app.analyzers.form_analyzer import FormAnalyzer
from app.schemas.pages import PageData


def make_page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def test_consent_analyzer_detects_form_consent_and_form_id() -> None:
    page = make_page(
        """
        <form id="callback">
          <input name="phone" />
          <button>Отправить</button>
          <p>Нажимая кнопку, я соглашаюсь на обработку персональных данных.</p>
        </form>
        """
    )
    forms = FormAnalyzer().analyze([page])

    result = ConsentAnalyzer().analyze([page], forms)

    assert result.found is True
    assert result.items[0].form_id == "callback"
    assert result.items[0].consent_type == "personal_data"


def test_consent_analyzer_returns_empty_result_without_consent() -> None:
    page = make_page(
        """
        <form id="callback">
          <input name="phone" />
          <button>Отправить</button>
        </form>
        """
    )
    forms = FormAnalyzer().analyze([page])

    result = ConsentAnalyzer().analyze([page], forms)

    assert result.found is False
    assert result.items == []
