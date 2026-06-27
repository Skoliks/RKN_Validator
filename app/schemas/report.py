from pydantic import BaseModel, ConfigDict, Field


class ReportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    recommendations: list[str] = Field(default_factory=list)
