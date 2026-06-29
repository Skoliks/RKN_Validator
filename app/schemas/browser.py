from pydantic import BaseModel, ConfigDict, Field


class BrowserNetworkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    path: str | None = None
    has_query: bool = False
    original_url_truncated: bool = False
    method: str | None = None
    resource_type: str | None = None
    status_code: int | None = None
    domain: str | None = None
    is_third_party: bool


class BrowserCookieItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    domain: str | None = None
    path: str | None = None
    http_only: bool | None = None
    secure: bool | None = None
    same_site: str | None = None


class BrowserPageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    browser_check_performed: bool
    url: str
    final_url: str | None = None
    title: str | None = None
    visible_text: str | None = None
    cookies_after_load: list[BrowserCookieItem] = Field(default_factory=list)
    network_requests: list[BrowserNetworkRequest] = Field(default_factory=list)
    console_errors: list[str] = Field(default_factory=list)
    error_type: str | None = None
    message: str | None = None
    warnings: list[str] = Field(default_factory=list)


class CookieInteractionButton(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    action_type: str
    selector: str | None = None
    visible: bool
    enabled: bool


class CookieInteractionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    cookies: list[BrowserCookieItem] = Field(default_factory=list)
    network_requests: list[BrowserNetworkRequest] = Field(default_factory=list)
    cookies_count: int
    third_party_cookies_count: int
    analytics_requests_count: int
    advertising_requests_count: int
    third_party_requests_count: int


class CookieInteractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    performed: bool
    banner_found: bool
    buttons_found: list[CookieInteractionButton] = Field(default_factory=list)
    reject_clicked: bool
    accept_clicked: bool
    reject_click_error: str | None = None
    accept_click_error: str | None = None
    initial_snapshot: CookieInteractionSnapshot | None = None
    after_reject_snapshot: CookieInteractionSnapshot | None = None
    after_accept_snapshot: CookieInteractionSnapshot | None = None
    cookies_reduced_after_reject: bool | None = None
    analytics_reduced_after_reject: bool | None = None
    advertising_reduced_after_reject: bool | None = None
    warnings: list[str] = Field(default_factory=list)


class BrowserCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    performed: bool
    pages_checked: int
    items: list[BrowserPageResult] = Field(default_factory=list)
    cookie_interaction: CookieInteractionResult | None = None
    warnings: list[str] = Field(default_factory=list)
