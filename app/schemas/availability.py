from pydantic import BaseModel, ConfigDict


class AvailabilityInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    status_code: int | None = None
    error_type: str | None = None
    message: str | None = None
