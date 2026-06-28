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

## Future iterations after MVP

These items are future scope only. They must not expand the current MVP and must follow `PROJECT_RULES.md` layering and tooling constraints.

- OwnerRequisitesAnalyzer improvements: improve completeness scoring, legal-address confidence, and privacy-contact context.
- DomainComplianceAnalyzer improvements: add optional manual evidence fields for registrar and administrator checks without whois or external APIs.
- CookieAnalyzer: use static HTML and optional browser outputs to detect cookie banners, accept/decline controls, and optional cookie or tracking scripts that appear before consent.
- AdvertisingAnalyzer: detect advertising labels, advertiser mentions, and `erid` tokens.
- AccessibilityAnalyzer: perform lightweight static accessibility checks such as missing alt text, weak link text, heading structure, and language attributes.
- HostingLocationAnalyzer: collect technical hosting hints and manual evidence for hosting/provider localization checks without external APIs in the MVP.
- RknOperatorAnalyzer: document and collect manual evidence for RKN personal data operator notification status without external APIs in the MVP.
