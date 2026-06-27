from pydantic import BaseModel, ConfigDict, Field


class RiskFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    title: str
    score: int
    description: str | None = None


class RiskAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_score: int = 0
    level: str
    factors: list[RiskFactor] = Field(default_factory=list)
