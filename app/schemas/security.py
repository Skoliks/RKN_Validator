from pydantic import BaseModel, ConfigDict, Field


class InsecureFormAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_url: str
    action: str | None = None
    reason: str


class MixedContentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_url: str
    url: str
    tag: str | None = None
    attribute: str | None = None


class SecurityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    https_enabled: bool | None = None
    has_mixed_content: bool | None = None
    mixed_content_items: list[MixedContentItem] = Field(default_factory=list)
    insecure_form_actions: list[InsecureFormAction] = Field(default_factory=list)
