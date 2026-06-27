from app.analyzers.russian_market_analyzer import RussianMarketAnalyzer
from app.schemas.pages import PageData


def make_page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def test_russian_market_analyzer_detects_inn_and_ru_phone() -> None:
    page = make_page("<p>ИНН 7701234567, телефон +7 (495) 123-45-67</p>")

    result = RussianMarketAnalyzer().analyze([page])

    signal_types = {signal.signal_type for signal in result.signals}
    assert result.found is True
    assert "inn" in signal_types
    assert "phone_ru" in signal_types


def test_russian_market_analyzer_returns_empty_result_without_ru_signals() -> None:
    page = make_page("<p>Company number 123. Contact us by email.</p>")

    result = RussianMarketAnalyzer().analyze([page])

    assert result.found is False
    assert result.signals == []
