from pydantic import BaseModel, ConfigDict, Field


class InsecureFormAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_url: str
    action: str | None = None
    reason: str


class SecurityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    https_enabled: bool | None = None
    has_mixed_content: bool | None = None
    insecure_form_actions: list[InsecureFormAction] = Field(default_factory=list)
