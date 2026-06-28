from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.authentication import AuthProviderItem, AuthenticationResult
from app.schemas.pages import PageData


class AuthProviderAnalyzer:
    text_markers = {
        "Google": (
            "войти через google",
            "sign in with google",
            "continue with google",
            "login with google",
        ),
        "Facebook": (
            "sign in with facebook",
            "continue with facebook",
            "login with facebook",
            "log in with facebook",
        ),
    }
    domain_markers = {
        "accounts.google.com": "Google",
        "appleid.apple.com": "Apple",
        "login.microsoftonline.com": "Microsoft",
    }
    auth_path_markers = (
        "login",
        "oauth",
        "authorize",
        "signin",
        "sign-in",
        "signup",
        "sso",
    )
    auth_query_markers = ("oauth", "client_id", "redirect_uri", "response_type", "scope")
    provider_auth_domains = {
        "facebook.com": "Facebook",
    }

    def analyze(self, pages: list[PageData]) -> AuthenticationResult:
        providers: list[AuthProviderItem] = []
        seen: set[tuple[str, str | None, str | None]] = set()

        for page in pages:
            if not page.html:
                continue

            page_url = page.final_url or page.url
            soup = BeautifulSoup(page.html, "html.parser")
            page_text = soup.get_text(" ", strip=True).lower()

            for provider, markers in self.text_markers.items():
                if any(marker in page_text for marker in markers):
                    self._append_provider(providers, seen, provider, page_url, None)

            for anchor in soup.find_all(["a", "form"], href=True):
                if isinstance(anchor, Tag):
                    self._detect_domain_provider(anchor.get("href"), page_url, providers, seen)

            for form in soup.find_all("form", action=True):
                if isinstance(form, Tag):
                    self._detect_domain_provider(form.get("action"), page_url, providers, seen)

        return AuthenticationResult(found=bool(providers), providers=providers)

    def _detect_domain_provider(
        self,
        raw_url,
        page_url: str,
        providers: list[AuthProviderItem],
        seen: set[tuple[str, str | None, str | None]],
    ) -> None:
        if not isinstance(raw_url, str):
            return

        url = urljoin(page_url, raw_url.strip())
        domain = urlsplit(url).hostname
        if not domain:
            return

        domain = domain.lower().rstrip(".")
        for marker, provider in self.domain_markers.items():
            if domain == marker or domain.endswith(f".{marker}"):
                self._append_provider(providers, seen, provider, page_url, url)
                return

        for marker, provider in self.provider_auth_domains.items():
            if (
                domain == marker or domain.endswith(f".{marker}")
            ) and self._has_auth_intent(url):
                self._append_provider(providers, seen, provider, page_url, url)

    def _has_auth_intent(self, url: str) -> bool:
        parsed = urlsplit(url)
        path = parsed.path.lower()
        query = parsed.query.lower()
        return any(marker in path for marker in self.auth_path_markers) or any(
            marker in query for marker in self.auth_query_markers
        )

    def _append_provider(
        self,
        providers: list[AuthProviderItem],
        seen: set[tuple[str, str | None, str | None]],
        provider: str,
        page_url: str,
        url: str | None,
    ) -> None:
        key = (provider, page_url, url)
        if key in seen:
            return

        seen.add(key)
        providers.append(AuthProviderItem(provider=provider, page_url=page_url, url=url))
