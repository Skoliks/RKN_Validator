from app.schemas.authentication import AuthProviderItem, AuthenticationResult
from app.schemas.availability import AvailabilityInfo
from app.schemas.browser import (
    BrowserCheckResult,
    BrowserCookieItem,
    BrowserNetworkRequest,
    BrowserPageResult,
)
from app.schemas.check import CheckMeta, CheckRequest, CheckResult
from app.schemas.consents import ConsentItem, ConsentsResult
from app.schemas.cookies import (
    CookieAnalysisResult,
    CookieBannerCandidate,
    CookieBeforeConsentItem,
    CookieNetworkRequestItem,
)
from app.schemas.domain_compliance import DomainComplianceResult
from app.schemas.external_services import ExternalServiceItem, ExternalServicesResult
from app.schemas.forms import FormField, FormItem, FormsResult
from app.schemas.owner_requisites import OwnerRequisiteItem, OwnerRequisitesResult
from app.schemas.pages import CrawlResult, PageData, PageItem, PagesResult, WarningItem
from app.schemas.policy import PolicyMatchedLink, PolicyResult
from app.schemas.report import ReportResult
from app.schemas.risk import RiskAssessment, RiskFactor
from app.schemas.russian_market import RussianMarketResult, RussianMarketSignal
from app.schemas.security import InsecureFormAction, SecurityResult
from app.schemas.site import SiteInfo

__all__ = [
    "AuthProviderItem",
    "AuthenticationResult",
    "AvailabilityInfo",
    "BrowserCheckResult",
    "BrowserCookieItem",
    "BrowserNetworkRequest",
    "BrowserPageResult",
    "CheckMeta",
    "CheckRequest",
    "CheckResult",
    "ConsentItem",
    "ConsentsResult",
    "CookieAnalysisResult",
    "CookieBannerCandidate",
    "CookieBeforeConsentItem",
    "CookieNetworkRequestItem",
    "CrawlResult",
    "DomainComplianceResult",
    "ExternalServiceItem",
    "ExternalServicesResult",
    "FormField",
    "FormItem",
    "FormsResult",
    "InsecureFormAction",
    "OwnerRequisiteItem",
    "OwnerRequisitesResult",
    "PageData",
    "PageItem",
    "PagesResult",
    "PolicyMatchedLink",
    "PolicyResult",
    "ReportResult",
    "RiskAssessment",
    "RiskFactor",
    "RussianMarketResult",
    "RussianMarketSignal",
    "SecurityResult",
    "SiteInfo",
    "WarningItem",
]
