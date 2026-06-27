from app.analyzers.auth_provider_analyzer import AuthProviderAnalyzer
from app.schemas.pages import PageData


def make_page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def test_auth_provider_analyzer_detects_google_text() -> None:
    page = make_page("<button>Войти через Google</button>")

    result = AuthProviderAnalyzer().analyze([page])

    assert result.found is True
    assert result.providers[0].provider == "Google"


def test_auth_provider_analyzer_detects_google_accounts_domain() -> None:
    page = make_page('<a href="https://accounts.google.com/o/oauth2/v2/auth">Login</a>')

    result = AuthProviderAnalyzer().analyze([page])

    assert result.found is True
    assert result.providers[0].provider == "Google"
    assert result.providers[0].url == "https://accounts.google.com/o/oauth2/v2/auth"
