from pydantic import BaseModel, ConfigDict


class ReportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    recommendation: str
    llm_generated: bool = False
