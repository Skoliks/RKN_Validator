from pydantic import BaseModel, ConfigDict, Field


class InfrastructureDomainItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    category: str
    is_third_party: bool
    likely_foreign: bool | None = None
    likely_russian: bool | None = None
    source: str
    evidence: str | None = None


class InfrastructureServiceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    category: str
    domain: str
    likely_foreign: bool | None = None
    likely_russian: bool | None = None
    source: str
    evidence: str | None = None


class InfrastructureAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checked: bool = False
    external_domains_found: bool = False
    foreign_services_found: bool = False
    russian_services_found: bool = False
    cdn_services_found: bool = False
    analytics_services_found: bool = False
    advertising_services_found: bool = False
    video_services_found: bool = False
    fonts_services_found: bool = False
    social_services_found: bool = False
    messenger_services_found: bool = False
    crm_services_found: bool = False
    payment_services_found: bool = False
    maps_services_found: bool = False
    domains_count: int = 0
    foreign_domains_count: int = 0
    russian_domains_count: int = 0
    domains: list[InfrastructureDomainItem] = Field(default_factory=list)
    services: list[InfrastructureServiceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
