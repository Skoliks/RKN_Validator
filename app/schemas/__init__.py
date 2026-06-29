from app.schemas.accessibility import AccessibilityAnalysisResult, AccessibilityIssueItem
from app.schemas.authentication import AuthProviderItem, AuthenticationResult
from app.schemas.advertising import (
    AdvertisingAnalysisResult,
    AdvertisingServiceItem,
    AdvertisingTextItem,
)
from app.schemas.availability import AvailabilityInfo
from app.schemas.browser import (
    BrowserCheckResult,
    BrowserCookieItem,
    BrowserNetworkRequest,
    BrowserPageResult,
    CookieInteractionButton,
    CookieInteractionResult,
    CookieInteractionSnapshot,
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
from app.schemas.infrastructure import (
    InfrastructureAnalysisResult,
    InfrastructureDomainItem,
    InfrastructureServiceItem,
)
from app.schemas.owner_requisites import OwnerRequisiteItem, OwnerRequisitesResult
from app.schemas.pages import CrawlResult, PageData, PageItem, PagesResult, WarningItem
from app.schemas.policy import PolicyMatchedLink, PolicyResult
from app.schemas.report import ReportResult
from app.schemas.risk import RiskAssessment, RiskFactor
from app.schemas.russian_market import RussianMarketResult, RussianMarketSignal
from app.schemas.security import InsecureFormAction, SecurityResult
from app.schemas.site import SiteInfo

__all__ = [
    "AccessibilityAnalysisResult",
    "AccessibilityIssueItem",
    "AuthProviderItem",
    "AuthenticationResult",
    "AdvertisingAnalysisResult",
    "AdvertisingServiceItem",
    "AdvertisingTextItem",
    "AvailabilityInfo",
    "BrowserCheckResult",
    "BrowserCookieItem",
    "BrowserNetworkRequest",
    "BrowserPageResult",
    "CookieInteractionButton",
    "CookieInteractionResult",
    "CookieInteractionSnapshot",
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
    "InfrastructureAnalysisResult",
    "InfrastructureDomainItem",
    "InfrastructureServiceItem",
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
