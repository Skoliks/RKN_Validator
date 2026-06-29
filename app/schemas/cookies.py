from pydantic import BaseModel, ConfigDict, Field

from app.schemas.browser import CookieInteractionResult


class CookieBannerCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_url: str
    text: str
    accept_found: bool
    reject_found: bool
    settings_found: bool
    evidence: str | None = None


class CookieBeforeConsentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    domain: str | None = None
    is_third_party: bool
    category: str


class CookieNetworkRequestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    path: str | None = None
    domain: str | None = None
    resource_type: str | None = None
    category: str
    is_third_party: bool


class CookieAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    browser_check_available: bool = False
    analyzed: bool = False
    banner_found: bool = False
    accept_button_found: bool = False
    reject_button_found: bool = False
    settings_button_found: bool = False
    cookies_before_consent_found: bool = False
    third_party_cookies_before_consent_found: bool = False
    analytics_requests_before_consent_found: bool = False
    advertising_requests_before_consent_found: bool = False
    third_party_requests_before_consent_found: bool = False
    interaction_available: bool = False
    reject_button_found: bool = False
    accept_button_found: bool = False
    settings_button_found: bool = False
    reject_test_performed: bool = False
    accept_test_performed: bool = False
    cookies_reduced_after_reject: bool | None = None
    analytics_reduced_after_reject: bool | None = None
    advertising_reduced_after_reject: bool | None = None
    banner_candidates: list[CookieBannerCandidate] = Field(default_factory=list)
    cookies_before_consent: list[CookieBeforeConsentItem] = Field(default_factory=list)
    requests_before_consent: list[CookieNetworkRequestItem] = Field(default_factory=list)
    interaction: CookieInteractionResult | None = None
    warnings: list[str] = Field(default_factory=list)
    message: str | None = None
