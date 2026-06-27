from pydantic import BaseModel, ConfigDict, Field


class ConsentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_url: str
    consent_type: str
    text: str | None = None
    selector: str | None = None


class ConsentsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool = False
    items: list[ConsentItem] = Field(default_factory=list)
