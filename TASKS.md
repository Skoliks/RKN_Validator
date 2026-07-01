# Development Iterations

## Completed

1. Project skeleton - done.
2. Pydantic schemas and internal models - done.
3. UrlService and user input normalization - done.
4. HttpClient, AvailabilityService, CrawlService - done.
5. Form, privacy policy, and external services analyzers - done.
6. ConsentAnalyzer, HttpsAnalyzer, AuthProviderAnalyzer, RussianMarketAnalyzer - done.
7. RiskService - done.
8. ReportService - done.
9. CheckService orchestration - done.
10. `POST /check` endpoint - done.
11. Initial Docker, README, and MVP verification - done.
12. OwnerRequisitesAnalyzer - done.
13. DomainComplianceAnalyzer - done.
14. BrowserClient - done.
15. CookieAnalyzer - done.
16. Cookie interaction check - done.
17. AdvertisingAnalyzer - done.
18. AccessibilityAnalyzer - done.
19. InfrastructureAnalyzer - done.
20A. Final report structure - done.
20B. Risk/JSON cleanup - done.
21. Docker + README + release cleanup - done.
22. Real sites reliability fixes - done.
23. Markdown report export - done.

## Backend MVP Status

Backend-MVP logic is complete. The service provides `GET /health`, `POST /check`, `POST /check/markdown`, structured risk assessment, and a final report with `summary`, `recommendations`, `checked_areas`, `manual_review_required`, and `limitations`.

## Future

- Export report to HTML/PDF.
- Frontend.
- Telegram bot.
- MCP interface.
- DB/history for previous checks.
- Queue/background checks.
- Docker/release hardening after MVP feedback.
- Optional external-source checks in a later version, if explicitly approved.
