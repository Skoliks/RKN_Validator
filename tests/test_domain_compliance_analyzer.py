from app.analyzers.domain_compliance_analyzer import DomainComplianceAnalyzer
from app.schemas.site import SiteInfo


def test_domain_compliance_ru_requires_manual_check() -> None:
    result = DomainComplianceAnalyzer().analyze(domain_zone="ru")

    assert result.zone == "ru"
    assert result.esia_identification_required is True
    assert result.applies_to_domain_zone is True
    assert result.manual_check_required is True
    assert result.status == "applicable_requires_manual_check"


def test_domain_compliance_rf_requires_manual_check() -> None:
    result = DomainComplianceAnalyzer().analyze(domain_zone="рф")

    assert result.zone == "рф"
    assert result.esia_identification_required is True
    assert result.applies_to_domain_zone is True


def test_domain_compliance_su_requires_manual_check() -> None:
    result = DomainComplianceAnalyzer().analyze(domain_zone="su")

    assert result.zone == "su"
    assert result.esia_identification_required is True
    assert result.applies_to_domain_zone is True


def test_domain_compliance_io_is_not_applicable() -> None:
    result = DomainComplianceAnalyzer().analyze(domain_zone="io")

    assert result.zone == "io"
    assert result.esia_identification_required is False
    assert result.applies_to_domain_zone is False
    assert result.status == "not_applicable"


def test_domain_compliance_com_is_not_applicable() -> None:
    result = DomainComplianceAnalyzer().analyze(domain_zone="com")

    assert result.zone == "com"
    assert result.esia_identification_required is False
    assert result.applies_to_domain_zone is False


def test_domain_compliance_normalizes_zone_with_dot() -> None:
    result = DomainComplianceAnalyzer().analyze(domain_zone=".ru")

    assert result.zone == "ru"
    assert result.applies_to_domain_zone is True


def test_domain_compliance_empty_zone_is_unknown() -> None:
    result = DomainComplianceAnalyzer().analyze(domain_zone=None)

    assert result.zone is None
    assert result.status == "unknown"
    assert result.warnings == ["Не удалось определить доменную зону."]


def test_domain_compliance_can_use_site_info() -> None:
    site = SiteInfo(
        original_input="example.ru",
        normalized_url="https://example.ru",
        final_url="https://example.ru",
        domain="example.ru",
        domain_zone="ru",
    )

    result = DomainComplianceAnalyzer().analyze(site)

    assert result.zone == "ru"
    assert result.applies_to_domain_zone is True
