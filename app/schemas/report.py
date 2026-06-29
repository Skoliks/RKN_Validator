from pydantic import BaseModel, ConfigDict


class ReportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: list[str]
    recommendations: list[str]
    checked_areas: list[str]
    manual_review_required: list[str]
    limitations: list[str]
    recommendation: str = ""
    llm_generated: bool = False
