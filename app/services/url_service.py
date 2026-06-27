import re
from urllib.parse import SplitResult, urlsplit, urlunsplit

from app.core.exceptions import InvalidUrlError, InvalidUserInputError
from app.schemas.site import SiteInfo


class UrlService:
    allowed_schemes = {"http", "https"}
    domain_label_pattern = re.compile(r"^[a-z0-9-]+$")

    def normalize(self, user_input: str) -> SiteInfo:
        raw_value = user_input.strip()
        if not raw_value:
            raise InvalidUserInputError()

        if self._contains_whitespace(raw_value):
            raise InvalidUserInputError()

        value = raw_value if "://" in raw_value else f"https://{raw_value}"
        parsed = urlsplit(value)

        if parsed.scheme not in self.allowed_schemes or not parsed.netloc:
            raise InvalidUrlError()

        domain = parsed.hostname
        if not domain:
            raise InvalidUrlError()

        domain = domain.rstrip(".").lower()
        if not self._looks_like_domain(domain):
            raise InvalidUrlError()

        port = self._get_port(parsed)
        normalized_url = self._build_normalized_url(parsed.scheme, domain, port)
        final_url = self._build_final_url(parsed.scheme, domain, port, parsed.path, parsed.query)

        return SiteInfo(
            original_input=user_input,
            normalized_url=normalized_url,
            final_url=final_url,
            domain=domain,
            domain_zone=self._get_domain_zone(domain),
        )

    def _build_normalized_url(self, scheme: str, domain: str, port: int | None) -> str:
        netloc = self._build_netloc(domain, port)
        return urlunsplit((scheme, netloc, "", "", ""))

    def _build_final_url(
        self,
        scheme: str,
        domain: str,
        port: int | None,
        path: str,
        query: str,
    ) -> str:
        normalized_path = "" if path == "/" else path
        netloc = self._build_netloc(domain, port)
        return urlunsplit((scheme, netloc, normalized_path, query, ""))

    def _build_netloc(self, domain: str, port: int | None) -> str:
        return f"{domain}:{port}" if port else domain

    def _get_domain_zone(self, domain: str) -> str | None:
        labels = domain.split(".")
        return labels[-1] if len(labels) > 1 else None

    def _get_port(self, parsed_url: SplitResult) -> int | None:
        try:
            return parsed_url.port
        except ValueError as exc:
            raise InvalidUrlError() from exc

    def _looks_like_domain(self, domain: str) -> bool:
        if "." not in domain:
            return False

        labels = domain.split(".")
        return all(self._is_valid_domain_label(label) for label in labels)

    def _is_valid_domain_label(self, label: str) -> bool:
        if not label or len(label) > 63 or label.startswith("-") or label.endswith("-"):
            return False

        try:
            ascii_label = label.encode("idna").decode("ascii")
        except UnicodeError:
            return False

        return bool(self.domain_label_pattern.fullmatch(ascii_label))

    def _contains_whitespace(self, value: str) -> bool:
        return any(char.isspace() for char in value)
