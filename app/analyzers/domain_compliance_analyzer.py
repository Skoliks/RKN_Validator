from app.schemas.domain_compliance import DomainComplianceResult
from app.schemas.site import SiteInfo


class DomainComplianceAnalyzer:
    applicable_zones = {"ru", "рф", "su"}

    applicable_recommendations = [
        "Проверить администратора домена у регистратора.",
        "Проверить наличие подтверждённой учётной записи ЕСИА у администратора.",
        "Проверить совпадение данных администратора у регистратора и в ЕСИА.",
    ]
    not_applicable_recommendations = [
        "Остальные требования к сайту необходимо проверять независимо от доменной зоны."
    ]

    def analyze(
        self,
        site: SiteInfo | None = None,
        domain: str | None = None,
        domain_zone: str | None = None,
    ) -> DomainComplianceResult:
        zone = self._normalize_zone(domain_zone or self._zone_from_site_or_domain(site, domain))

        if not zone:
            return DomainComplianceResult(
                zone=None,
                status="unknown",
                message="Доменная зона не определена. Требуется ручная проверка применимости требований.",
                recommendations=self.not_applicable_recommendations.copy(),
                warnings=["Не удалось определить доменную зону."],
            )

        if zone in self.applicable_zones:
            return DomainComplianceResult(
                zone=zone,
                esia_identification_required=True,
                applies_to_domain_zone=True,
                manual_check_required=True,
                status="applicable_requires_manual_check",
                message=(
                    f"Домен находится в зоне .{zone}. Для таких доменов требуется ручная проверка "
                    "идентификации администратора через ЕСИА."
                ),
                recommendations=self.applicable_recommendations.copy(),
                warnings=[],
            )

        return DomainComplianceResult(
            zone=zone,
            esia_identification_required=False,
            applies_to_domain_zone=False,
            manual_check_required=False,
            status="not_applicable",
            message=(
                "Домен находится вне зон .ru, .рф, .su. Требование идентификации администратора "
                "через ЕСИА к этой доменной зоне не применяется."
            ),
            recommendations=self.not_applicable_recommendations.copy(),
            warnings=[],
        )

    def _zone_from_site_or_domain(
        self,
        site: SiteInfo | None,
        domain: str | None,
    ) -> str | None:
        if site and site.domain_zone:
            return site.domain_zone

        source_domain = domain or (site.domain if site else None)
        if not source_domain or "." not in source_domain:
            return None

        return source_domain.rsplit(".", 1)[-1]

    def _normalize_zone(self, zone: str | None) -> str | None:
        if not zone:
            return None

        normalized = zone.strip().lower().lstrip(".")
        return normalized or None
