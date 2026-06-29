# Development Iterations

## Iteration 1
Базовый скелет проекта.

## Iteration 2
Pydantic-схемы и внутренние модели.

## Iteration 3
UrlService и обработка пользовательского ввода.

## Iteration 4
HttpClient, AvailabilityService и CrawlService.

## Iteration 5
Анализаторы форм, политики и внешних сервисов.

## Iteration 6
ConsentAnalyzer, HttpsAnalyzer, AuthProviderAnalyzer, RussianMarketAnalyzer.

## Iteration 7
RiskService.

## Iteration 8
ReportService.

## Iteration 9
CheckService и сборка полного потока.

## Iteration 10
Endpoint POST /check.

## Iteration 11
Docker, README и финальная проверка MVP.

## Iteration 12
OwnerRequisitesAnalyzer: отдельное извлечение реквизитов владельца сайта из уже загруженных страниц без внешних API.

## Iteration 13
DomainComplianceAnalyzer: определение применимости ручной проверки идентификации администратора через ЕСИА по зонам `.ru`, `.рф`, `.su` без whois, внешних API и автоматического повышения риска.

## Iteration 14
BrowserClient on Playwright: optional browser infrastructure for collecting cookies, network requests, and console errors when enabled; no CookieAnalyzer, risk scoring, screenshots, clicks, or form submission.

## Iteration 15
CookieAnalyzer on BrowserCheck data: preliminary detection of cookie-banner text, cookies after initial page load before explicit user choice, and third-party analytics or advertising requests; no clicks, screenshots, form submission, or legal conclusions.

## Iteration 16
Browser cookie interaction check: optional Playwright scenario for recognized cookie accept/reject buttons in isolated contexts; no forms, screenshots, business CTA clicks, external APIs, or legal conclusions.

## Iteration 17
AdvertisingAnalyzer: preliminary detection of advertising services, `erid`, explicit ad labels, advertiser mentions, and possible ad blocks from crawled HTML, external service findings, and optional browser network data. The result is exposed as `advertising` in `CheckResult`; it does not make legal conclusions and requires manual review.

## Iteration 18
AccessibilityAnalyzer: preliminary static accessibility check for missing `html lang`, image `alt`, empty links/buttons, missing form labels, iframe titles, heading-order warnings, and duplicate `id` values. The result is exposed as `accessibility` in `CheckResult`; it does not replace a full accessibility audit and does not make legal conclusions.

## Iteration 19
InfrastructureAnalyzer: preliminary analysis of third-party infrastructure domains and known service categories from crawled HTML, external service findings, optional browser network data, cookie analysis, and advertising analysis. It is exposed as `infrastructure` in `CheckResult`; it does not use Whois/GeoIP/external APIs and does not determine factual hosting country or data storage location.

## Iteration 20
Final report polishing: `ReportService` returns structured `summary`, `recommendations`, `checked_areas`, `manual_review_required`, and `limitations`. The report keeps cautious wording, avoids legal conclusions, preserves existing cookie/advertising/accessibility/infrastructure/security/domain/owner signals, and keeps browser-dependent limitations explicit when browser checks are disabled. `RiskService` consistency was tightened for score caps, preliminary-only factors, evidence size, query/base64 noise, and duplicate factor codes.

## Iteration 20B
Risk/JSON cleanup and final regression: backend-MVP logic is complete. `RiskService` keeps scores within 0..100, caps preliminary-only findings at medium/85, deduplicates factor codes and evidence, limits evidence size, and removes noisy base64/query evidence from risk output. Final regression covers structured report fields and `/check` modes with browser check disabled, browser check enabled, and cookie interaction enabled.

## Future iterations after MVP

These items are future scope only. They must not expand the current MVP and must follow `PROJECT_RULES.md` layering and tooling constraints.

- Packaging and Docker hardening for deployment.
- Exportable reports.
- Frontend, Telegram, and MCP integrations later, outside the backend MVP.
- OwnerRequisitesAnalyzer improvements: improve completeness scoring, legal-address confidence, and privacy-contact context.
- DomainComplianceAnalyzer improvements: add optional manual evidence fields for registrar and administrator checks without whois or external APIs.
- CookieAnalyzer improvements: improve banner extraction, consent-control interpretation, and cookie category confidence without making legal conclusions.
- AdvertisingAnalyzer improvements: improve ad block context, service taxonomy, and evidence grouping without legal conclusions or external APIs.
- AccessibilityAnalyzer improvements: improve context, grouping, and severity confidence without replacing a full accessibility audit.
- InfrastructureAnalyzer improvements: improve category confidence and manual evidence grouping without Whois, GeoIP, or external APIs.
- HostingLocationAnalyzer: collect manual evidence for hosting/provider localization checks without external APIs in the MVP.
- RknOperatorAnalyzer: document and collect manual evidence for RKN personal data operator notification status without external APIs in the MVP.
