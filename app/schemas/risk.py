from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RiskFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    level: Literal["low", "medium", "high"]
    score: int
    message: str
    evidence: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_score: int = 0
    level: Literal["low", "medium", "high"]
    factors: list[RiskFactor] = Field(default_factory=list)
