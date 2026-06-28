# MVP Coverage

This table maps the extended compliance scope to the current MVP implementation. "Current MVP coverage" describes the implemented product now, not the desired final product.

| Requirement | Current MVP coverage | Current module | What to add | Automatability |
|---|---|---|---|---|
| Domain zone identification for `.ru`, `.рф`, `.su` | Yes | `UrlService`, `SiteInfo`, `DomainComplianceAnalyzer` | Keep wording cautious and manual-review oriented | High |
| Domain administrator / registrar identification status | No | `DomainComplianceAnalyzer` only explains applicability by zone | Manual checklist fields or future domain evidence workflow; no external API or whois in MVP | Manual |
| User authorization detection | Partially | `AuthProviderAnalyzer` | Broaden provider patterns, separate login widgets from ordinary links, add Russian allowed-provider classification | Medium |
| Foreign OAuth / social login risk signals | Partially | `AuthProviderAnalyzer`, `RiskService` | Add provider allowlist/denylist and clearer evidence types | Medium |
| Personal data form detection | Yes | `FormAnalyzer` | Improve field taxonomy and multi-step form hints | High |
| Consent near personal data forms | Partially | `ConsentAnalyzer` | Detect separate consent documents and stronger proximity/context rules | Medium |
| Privacy / confidentiality document detection | Partially | `PolicyAnalyzer` | Improve document scoring and distinguish policy, consent, terms, and privacy notice | Medium |
| Cookie banner and optional cookie consent | No | None | `CookieAnalyzer` for banner text, accept/decline controls, and pre-consent optional scripts | Medium |
| Owner requisites: name, INN, OGRN/OGRNIP, address, contacts | Partially | `OwnerRequisitesAnalyzer` | Improve completeness scoring and distinguish weak address hints from full legal address | High |
| Dedicated personal data request contact | Partially | `OwnerRequisitesAnalyzer` | Broaden privacy-contact patterns and connect them to policy document context | Medium |
| Personal data localization in Russia | No | None | `HostingLocationAnalyzer` and manual evidence fields; avoid external APIs in MVP | Low |
| RKN personal data operator notification | No | None | `RknOperatorAnalyzer` as future/manual workflow; no registry API in MVP | Manual |
| Advertising label detection | No | None | `AdvertisingAnalyzer` to detect "Реклама", advertiser markers, and ad blocks | Medium |
| ERID token detection | No | None | `AdvertisingAnalyzer` to detect `erid` in URLs/text and associate it with ad-like blocks | High |
| Accessibility baseline | No | None | `AccessibilityAnalyzer` for static checks: missing alt, headings, link text, language attributes | Medium |
| Hosting provider registry status | No | None | `HostingLocationAnalyzer` with manual inputs or offline evidence; no external API in MVP | Low |
| Russian-language / Russian-market orientation | Partially | `RussianMarketAnalyzer` | Improve language ratio, Russian legal entity signals, ruble/pricing/context detection | High |
| External services and resources | Partially | `ExternalServicesAnalyzer`, `RiskService` | Split resource, analytics, CRM widget, CDN, social link, messenger, and auth categories consistently | High |
| HTTPS and insecure forms | Yes | `HttpsAnalyzer` | Expand mixed-content reporting and certificate metadata if available from existing HTTP response data | High |
| Mixed content on HTTPS pages | Partially | `HttpsAnalyzer` | Broaden static resource attributes and report severity separately from form security | High |
| Social networks / channels over 10,000 subscribers | No | `ExternalServicesAnalyzer` only classifies links | Future social-channel checklist; subscriber count and RKN registry status remain manual without external APIs | Manual |
| Report wording without legal conclusions | Partially | `ReportService` | Continue replacing categorical wording with technical evidence and manual-review recommendations | High |
| Risk scoring from analyzer outputs only | Yes | `RiskService` | Keep new checks as analyzer outputs; do not parse HTML in `RiskService` | High |

## MVP Boundary

The current MVP is a synchronous backend pre-check. It should not be expanded by this documentation update. New checks listed above belong to future iterations and must respect `PROJECT_RULES.md`.
