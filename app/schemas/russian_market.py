from pydantic import BaseModel, ConfigDict, Field


class RussianMarketSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_type: str
    page_url: str
    value: str | None = None


class RussianMarketResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool = False
    signals: list[RussianMarketSignal] = Field(default_factory=list)
