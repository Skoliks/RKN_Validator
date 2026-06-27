from pydantic import BaseModel, ConfigDict


class SiteInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_input: str
    normalized_url: str
    final_url: str | None = None
    domain: str
    domain_zone: str | None = None
