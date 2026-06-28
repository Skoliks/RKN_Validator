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


def test_auth_provider_analyzer_ignores_regular_facebook_company_link() -> None:
    page = make_page('<a href="https://facebook.com/company">Facebook</a>')

    result = AuthProviderAnalyzer().analyze([page])

    assert result.found is False
    assert result.providers == []


def test_auth_provider_analyzer_detects_login_with_facebook_text() -> None:
    page = make_page("<button>Login with Facebook</button>")

    result = AuthProviderAnalyzer().analyze([page])

    assert result.found is True
    assert result.providers[0].provider == "Facebook"


def test_auth_provider_analyzer_detects_facebook_oauth_link() -> None:
    page = make_page(
        '<a href="https://facebook.com/dialog/oauth?client_id=123">Login</a>'
    )

    result = AuthProviderAnalyzer().analyze([page])

    assert result.found is True
    assert result.providers[0].provider == "Facebook"
