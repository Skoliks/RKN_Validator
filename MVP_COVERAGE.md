# MVP Coverage

Backend-MVP выполняет предварительную техническую проверку сайта и возвращает структурированный JSON-результат через `POST /check`.

## Что входит в MVP

- URL normalization.
- Availability check.
- Ограниченный crawl страниц.
- FormAnalyzer.
- ConsentAnalyzer.
- PolicyAnalyzer.
- ExternalServicesAnalyzer.
- HttpsAnalyzer для HTTPS и mixed content.
- RussianMarketAnalyzer.
- OwnerRequisitesAnalyzer.
- DomainComplianceAnalyzer для применимости ЕСИА по зоне `.ru`, `.рф`, `.su`.
- Опциональный BrowserClient на Playwright.
- CookieAnalyzer.
- Cookie interaction check.
- AdvertisingAnalyzer.
- AccessibilityAnalyzer.
- InfrastructureAnalyzer.
- RiskService.
- Structured ReportService.
- `GET /health`.
- `POST /check`.
- Dockerfile и docker-compose для MVP-запуска.

## Что не входит в MVP

- Юридическое заключение.
- Подтверждение нарушения или соответствия требованиям.
- Whois.
- GeoIP.
- РКН API и другие внешние API.
- LLM.
- Telegram bot.
- MCP interface.
- База данных и история проверок.
- Redis.
- Celery или фоновые очереди.
- Авторизация.
- Frontend.

## Ограничения

- Проверяются только доступные страницы.
- Browser check зависит от региона, устройства, сессии и состояния сайта.
- Сервис не определяет фактическое место хранения персональных данных.
- Cookie, advertising, accessibility и infrastructure findings требуют ручной проверки.
- AccessibilityAnalyzer не заменяет полноценный аудит доступности.
- AdvertisingAnalyzer не подтверждает и не исключает нарушение.

## Реализованные анализаторы

- `FormAnalyzer`
- `ConsentAnalyzer`
- `PolicyAnalyzer`
- `ExternalServicesAnalyzer`
- `HttpsAnalyzer`
- `RussianMarketAnalyzer`
- `OwnerRequisitesAnalyzer`
- `DomainComplianceAnalyzer`
- `CookieAnalyzer`
- `AdvertisingAnalyzer`
- `AccessibilityAnalyzer`
- `InfrastructureAnalyzer`

## Будущие версии

- Export report в Markdown/HTML/PDF.
- Frontend.
- Telegram bot.
- MCP interface.
- DB/history.
- Queue/background checks.
- Расширенные проверки через внешние источники, если они будут явно разрешены.
