from app.analyzers.auth_provider_analyzer import AuthProviderAnalyzer
from app.analyzers.consent_analyzer import ConsentAnalyzer
from app.analyzers.cookie_analyzer import CookieAnalyzer
from app.analyzers.domain_compliance_analyzer import DomainComplianceAnalyzer
from app.analyzers.external_services_analyzer import ExternalServicesAnalyzer
from app.analyzers.form_analyzer import FormAnalyzer
from app.analyzers.https_analyzer import HttpsAnalyzer
from app.analyzers.owner_requisites_analyzer import OwnerRequisitesAnalyzer
from app.analyzers.policy_analyzer import PolicyAnalyzer
from app.analyzers.russian_market_analyzer import RussianMarketAnalyzer

__all__ = [
    "AuthProviderAnalyzer",
    "ConsentAnalyzer",
    "CookieAnalyzer",
    "DomainComplianceAnalyzer",
    "ExternalServicesAnalyzer",
    "FormAnalyzer",
    "HttpsAnalyzer",
    "OwnerRequisitesAnalyzer",
    "PolicyAnalyzer",
    "RussianMarketAnalyzer",
]
