# Site Compliance Checker

MVP backend-сервис для первичной технической проверки сайтов на признаки потенциальных правовых рисков.

Сервис не выполняет юридическую экспертизу и не устанавливает факт нарушения законодательства. Он выявляет технические и документные признаки потенциального риска на проверенных страницах сайта, после чего рекомендуется ручная проверка.

## Границы MVP

В MVP реализована синхронная проверка одного сайта через HTTP API:

- нормализация URL;
- проверка доступности сайта;
- ограниченный обход страниц;
- анализ форм, согласий, политики, внешних сервисов, HTTPS, cookie-признаков, рекламных признаков, иностранных провайдеров авторизации и признаков ориентации на российских пользователей;
- техническая оценка риска по балльной системе;
- шаблонный отчёт без LLM.

## Стек

- Python 3.12+
- FastAPI
- Pydantic v2
- pydantic-settings
- httpx
- BeautifulSoup4 + lxml
- tldextract
- Playwright (optional browser check)
- pytest, pytest-asyncio, pytest-httpx
- Docker / Docker Compose

## Локальный запуск

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Swagger/OpenAPI:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

## Запуск через Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Остановить:

```powershell
docker compose down
```

## Browser Check With Playwright

Браузерная проверка выключена по умолчанию и не меняет обычный `httpx`-пайплайн.

Установка Python-пакета:

```powershell
venv\Scripts\python.exe -m pip install playwright
```

Установка Chromium для Playwright выполняется отдельно:

```powershell
venv\Scripts\python.exe -m playwright install chromium
```

Включение:

```env
ENABLE_BROWSER_CHECK=true
```

Опциональная проверка взаимодействия с cookie-баннером выключена отдельно:

```env
ENABLE_COOKIE_INTERACTION_CHECK=true
```

`BrowserClient` собирает cookies после загрузки страницы, сетевые запросы, видимый текст страницы и ошибки консоли. `CookieAnalyzer` использует эти данные для предварительного выявления признаков cookie-баннера, cookies после первичной загрузки до явного выбора пользователя и сторонних запросов. При включённом `ENABLE_COOKIE_INTERACTION_CHECK` сервис пробует безопасно найти cookie-кнопки и отдельно проверить сценарии "отклонить" и "принять" в чистых browser context. Проверка остаётся предварительной: сервис не делает юридический вывод, не отправляет формы, не кликает по бизнес-кнопкам и не делает скриншоты.

`AdvertisingAnalyzer` добавляет отдельный блок `advertising` в результат проверки. Он предварительно ищет признаки рекламных сервисов, `erid`, явной маркировки рекламы, сведений о рекламодателе и возможных рекламных блоков по HTML-признакам, используя только уже собранные страницы, `ExternalServicesAnalyzer` и опциональные browser network данные. Блок не делает юридический вывод: автоматическая проверка не подтверждает и не исключает нарушение, а найденные признаки требуют ручной проверки.

`AccessibilityAnalyzer` adds a separate `accessibility` block. It performs a preliminary technical check of crawled HTML for missing `html lang`, image `alt`, empty links/buttons, missing form labels, iframe titles, heading-order warnings, and duplicate `id` values. It does not replace a full accessibility audit and does not make legal conclusions; findings require manual review.

`InfrastructureAnalyzer` adds a separate `infrastructure` block. It performs a preliminary analysis of third-party infrastructure domains and known service categories such as CDN, analytics, advertising, video, fonts, social, messenger, CRM, payment, maps, and API-like requests. It does not use Whois, GeoIP, RKN APIs, or external APIs, and it does not determine the factual hosting country or data storage location; findings require manual review.

## Примеры запросов

Healthcheck:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get
```

Проверка сайта:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/check" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"url":"example.ru"}'
```

Пример cURL:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/check \
  -H "Content-Type: application/json" \
  -d '{"url":"example.ru"}'
```

## Что не входит в MVP

- PostgreSQL
- Redis
- Celery / фоновые задачи
- Telegram-бот
- MCP-сервер
- LLM
- frontend
- авторизация пользователей
- история проверок
- массовая проверка сайтов

## Тесты

```powershell
venv\Scripts\python.exe -m pytest
```

## Final backend MVP report

The backend MVP now returns a structured `report` block in `POST /check`:

- `summary`: short ordered findings.
- `recommendations`: practical manual-review actions.
- `checked_areas`: areas that were actually checked.
- `manual_review_required`: items that need human confirmation.
- `limitations`: stable limitations of the automatic pre-check.

The implemented backend analyzers and services include `UrlService`, `AvailabilityService`, `CrawlService`, optional `BrowserClient`, `CookieAnalyzer`, cookie interaction check, `AdvertisingAnalyzer`, `AccessibilityAnalyzer`, `InfrastructureAnalyzer`, `OwnerRequisitesAnalyzer`, `DomainComplianceAnalyzer`, `ExternalServicesAnalyzer`, `RiskService`, `ReportService`, and `POST /check`.

The result is a preliminary technical review only. It is not a legal opinion, does not determine factual personal-data storage location, does not use Whois/GeoIP/RKN/external APIs, and requires manual review for legal or operational conclusions.

Next stages are packaging, Docker hardening, report export, and later optional frontend, Telegram, or MCP surfaces outside the backend MVP.
