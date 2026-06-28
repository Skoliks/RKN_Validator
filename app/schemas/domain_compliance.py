from pydantic import BaseModel, ConfigDict, Field


class DomainComplianceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone: str | None = None
    esia_identification_required: bool = False
    applies_to_domain_zone: bool = False
    manual_check_required: bool = False
    status: str = "unknown"
    message: str = ""
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
