import re

from bs4 import BeautifulSoup

from app.schemas.pages import PageData
from app.schemas.russian_market import RussianMarketResult, RussianMarketSignal


class RussianMarketAnalyzer:
    patterns = (
        ("russian_language", re.compile(r"[а-яё]", re.IGNORECASE)),
        ("phone_ru", re.compile(r"(?:\+7|8)\s*\(?\d{3}\)?[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")),
        ("inn", re.compile(r"\bинн\b|\b\d{10}\b|\b\d{12}\b", re.IGNORECASE)),
        ("ogrn", re.compile(r"\bогрн\b|\b\d{13}\b|\b\d{15}\b", re.IGNORECASE)),
        ("russian_address", re.compile(r"\b(россия|рф|москва|санкт-петербург|ул\.|улица|проспект)\b", re.IGNORECASE)),
        ("rubles", re.compile(r"\b(руб\.|рублей|рубль|₽)\b", re.IGNORECASE)),
    )

    def analyze(self, pages: list[PageData]) -> RussianMarketResult:
        signals: list[RussianMarketSignal] = []
        seen: set[tuple[str, str]] = set()

        for page in pages:
            if not page.html:
                continue

            page_url = page.final_url or page.url
            text = BeautifulSoup(page.html, "html.parser").get_text(" ", strip=True)

            for signal_type, pattern in self.patterns:
                match = pattern.search(text)
                if not match:
                    continue

                key = (signal_type, page_url)
                if key in seen:
                    continue

                seen.add(key)
                signals.append(
                    RussianMarketSignal(
                        signal_type=signal_type,
                        page_url=page_url,
                        value=match.group(0),
                    )
                )

        return RussianMarketResult(found=bool(signals), signals=signals)
