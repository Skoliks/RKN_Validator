from pydantic import BaseModel, ConfigDict, Field


class ExternalServiceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_type: str
    provider: str | None = None
    url: str | None = None
    page_url: str | None = None
    foreign: bool = True


class ExternalServicesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool = False
    items: list[ExternalServiceItem] = Field(default_factory=list)
