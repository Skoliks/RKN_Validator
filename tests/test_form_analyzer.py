from app.analyzers.form_analyzer import FormAnalyzer
from app.schemas.pages import PageData


def make_page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def test_form_analyzer_detects_name_phone_and_email_fields() -> None:
    html = """
    <form action="/send" method="post">
      <label for="name">Ваше имя</label>
      <input id="name" name="customer_name" />
      <label>Телефон <input name="phone" type="tel" /></label>
      <input name="email" type="email" placeholder="Email" required />
      <textarea name="message" placeholder="Сообщение"></textarea>
    </form>
    """

    result = FormAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.total == 1
    assert [field.field_type for field in result.items[0].fields] == [
        "name",
        "phone",
        "email",
        "message",
    ]
    assert result.items[0].method == "post"


def test_form_analyzer_returns_empty_result_without_forms() -> None:
    result = FormAnalyzer().analyze([make_page("<main>No forms</main>")])

    assert result.found is False
    assert result.total == 0
    assert result.items == []


def test_form_analyzer_handles_invalid_html() -> None:
    html = "<form><label>Телефон<input name='phone'"

    result = FormAnalyzer().analyze([make_page(html)])

    assert result.found is True
    assert result.items[0].fields[0].field_type == "phone"
