from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.authentication import AuthenticationResult
from app.schemas.availability import AvailabilityInfo
from app.schemas.consents import ConsentsResult
from app.schemas.external_services import ExternalServicesResult
from app.schemas.forms import FormsResult
from app.schemas.owner_requisites import OwnerRequisitesResult
from app.schemas.pages import PagesResult
from app.schemas.policy import PolicyResult
from app.schemas.report import ReportResult
from app.schemas.risk import RiskAssessment
from app.schemas.russian_market import RussianMarketResult
from app.schemas.security import SecurityResult
from app.schemas.site import SiteInfo


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str


class CheckMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "partial", "failed"]
    checked_at: datetime
    duration_ms: int
    mode: str
    interface: str


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site: SiteInfo
    check: CheckMeta
    availability: AvailabilityInfo | None = None
    pages: PagesResult | None = None
    owner_requisites: OwnerRequisitesResult | None = None
    russian_market: RussianMarketResult | None = None
    forms: FormsResult | None = None
    consents: ConsentsResult | None = None
    policy: PolicyResult | None = None
    external_services: ExternalServicesResult | None = None
    authentication: AuthenticationResult | None = None
    security: SecurityResult | None = None
    risk_assessment: RiskAssessment | None = None
    report: ReportResult | None = None
