from pydantic import BaseModel, ConfigDict, Field


class AuthProviderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    page_url: str | None = None
    url: str | None = None


class AuthenticationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool = False
    providers: list[AuthProviderItem] = Field(default_factory=list)
