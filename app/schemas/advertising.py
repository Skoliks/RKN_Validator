from pydantic import BaseModel, ConfigDict, Field


class AdvertisingServiceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_type: str
    provider: str
    url: str
    domain: str | None = None
    page_url: str | None = None
    source: str


class AdvertisingTextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: str
    value: str
    page_url: str
    evidence: str


class AdvertisingAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool = False
    ad_services_found: bool = False
    ad_marking_found: bool = False
    erid_found: bool = False
    advertiser_info_found: bool = False
    possible_ad_blocks_found: bool = False
    services: list[AdvertisingServiceItem] = Field(default_factory=list)
    text_items: list[AdvertisingTextItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
