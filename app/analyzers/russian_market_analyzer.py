import re

from bs4 import BeautifulSoup

from app.schemas.pages import PageData
from app.schemas.russian_market import RussianMarketResult, RussianMarketSignal


class RussianMarketAnalyzer:
    cyrillic_pattern = re.compile(r"[\u0400-\u04FF]")
    phone_pattern = re.compile(r"(?:\+7|8)\s*\(?\d{3}\)?[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")
    inn_number_pattern = re.compile(r"\b(?:\d{10}|\d{12})\b")
    ogrn_number_pattern = re.compile(r"\b(?:\d{13}|\d{15})\b")
    inn_word_pattern = re.compile(r"\bинн\b", re.IGNORECASE)
    ogrn_word_pattern = re.compile(r"\bогрн\b", re.IGNORECASE)
    address_pattern = re.compile(
        r"\b(россия|рф|москва|санкт-петербург|ул\.|улица|проспект)\b",
        re.IGNORECASE,
    )
    rubles_pattern = re.compile(r"\b(руб\.|рублей|рубль|₽)\b", re.IGNORECASE)

    def analyze(self, pages: list[PageData]) -> RussianMarketResult:
        signals: list[RussianMarketSignal] = []
        seen: set[tuple[str, str]] = set()

        for page in pages:
            if not page.html:
                continue

            page_url = page.final_url or page.url
            text = BeautifulSoup(page.html, "html.parser").get_text(" ", strip=True)

            self._append_language_signal(signals, seen, page_url, text)
            self._append_regex_signal(signals, seen, "phone_ru", page_url, self.phone_pattern, text)
            inn_found = self._append_regex_signal(
                signals,
                seen,
                "inn",
                page_url,
                self.inn_number_pattern,
                text,
            )
            ogrn_found = self._append_regex_signal(
                signals,
                seen,
                "ogrn",
                page_url,
                self.ogrn_number_pattern,
                text,
            )
            if not inn_found:
                self._append_regex_signal(
                    signals,
                    seen,
                    "inn_mentioned",
                    page_url,
                    self.inn_word_pattern,
                    text,
                )
            if not ogrn_found:
                self._append_regex_signal(
                    signals,
                    seen,
                    "ogrn_mentioned",
                    page_url,
                    self.ogrn_word_pattern,
                    text,
                )
            self._append_regex_signal(
                signals,
                seen,
                "russian_address",
                page_url,
                self.address_pattern,
                text,
            )
            self._append_regex_signal(signals, seen, "rubles", page_url, self.rubles_pattern, text)

        return RussianMarketResult(found=bool(signals), signals=signals)

    def _append_language_signal(
        self,
        signals: list[RussianMarketSignal],
        seen: set[tuple[str, str]],
        page_url: str,
        text: str,
    ) -> None:
        letters = [char for char in text if char.isalpha()]
        if not letters:
            return

        cyrillic_count = sum(1 for char in letters if self.cyrillic_pattern.match(char))
        ratio = cyrillic_count / len(letters)
        if ratio < 0.2 or cyrillic_count < 12:
            return

        self._append_signal(
            signals,
            seen,
            signal_type="russian_language",
            page_url=page_url,
            value=f"detected:{ratio:.0%}",
        )

    def _append_regex_signal(
        self,
        signals: list[RussianMarketSignal],
        seen: set[tuple[str, str]],
        signal_type: str,
        page_url: str,
        pattern: re.Pattern[str],
        text: str,
    ) -> bool:
        match = pattern.search(text)
        if not match:
            return False

        self._append_signal(signals, seen, signal_type, page_url, match.group(0))
        return True

    def _append_signal(
        self,
        signals: list[RussianMarketSignal],
        seen: set[tuple[str, str]],
        signal_type: str,
        page_url: str,
        value: str,
    ) -> None:
        key = (signal_type, page_url)
        if key in seen:
            return

        seen.add(key)
        signals.append(
            RussianMarketSignal(signal_type=signal_type, page_url=page_url, value=value)
        )
