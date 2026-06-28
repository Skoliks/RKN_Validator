from pydantic import BaseModel, ConfigDict, Field


class PolicyMatchedLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_url: str
    href: str
    text: str | None = None


class PolicyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_url: str
    url: str
    reason: str


class PolicyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool = False
    matched_links: list[PolicyMatchedLink] = Field(default_factory=list)
    candidates: list[PolicyCandidate] = Field(default_factory=list)
    policy_url: str | None = None
