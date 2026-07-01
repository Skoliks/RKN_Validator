# Site Compliance Checker

Backend-MVP сервис для предварительной технической проверки сайта по внешним признакам: cookies, сторонние сервисы, реклама, базовая доступность, внешняя инфраструктура, реквизиты владельца, HTTPS/mixed content и другие факторы.

Результат не является юридическим заключением. Сервис показывает технические признаки на проверенных страницах и формирует список пунктов для ручной проверки.

## Возможности MVP

- Нормализация URL.
- Проверка доступности сайта.
- Ограниченный crawl страниц.
- Анализ форм и признаков сбора данных.
- Поиск политики конфиденциальности.
- Анализ признаков согласий рядом с формами.
- Анализ внешних сервисов.
- Проверка HTTPS и mixed content.
- Поиск признаков российского рынка.
- Поиск реквизитов владельца сайта.
- Проверка применимости идентификации администратора домена через ЕСИА по доменной зоне.
- Опциональный browser check на Playwright.
- CookieAnalyzer для cookies и сетевых запросов до явного выбора пользователя.
- Опциональный cookie interaction check для распознанных cookie-кнопок.
- AdvertisingAnalyzer для рекламных сервисов, erid, маркировки и возможных рекламных блоков.
- AccessibilityAnalyzer для базовых технических признаков доступности.
- InfrastructureAnalyzer для сторонних доменов и категорий внешней инфраструктуры.
- Risk assessment.
- Structured report: `summary`, `recommendations`, `checked_areas`, `manual_review_required`, `limitations`.

## Ограничения

- Автоматическая проверка не является юридическим заключением.
- Проверяются только доступные страницы и данные, доступные на момент проверки.
- Динамическое поведение сайта может зависеть от региона, устройства, сессии и состояния сайта.
- Сервис не определяет фактическое место хранения персональных данных.
- Whois, GeoIP, РКН API и внешние API не используются.
- Accessibility check не заменяет полноценный аудит доступности.
- Advertising check не подтверждает и не исключает нарушение.
- Cookie check требует ручной проверки назначения cookies, баннера и возможности отклонения необязательных cookies.

## Быстрый запуск локально

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
uvicorn app.main:app --reload
```

Playwright нужен только для `ENABLE_BROWSER_CHECK=true`. При выключенном browser check обычная HTTP/BeautifulSoup проверка работает без запуска браузера.

## Запуск через Docker

```bash
cp .env.example .env
docker compose up --build
```

Проверка:

```bash
curl http://localhost:8000/health
```

Dockerfile устанавливает Chromium через Playwright. Browser check внутри контейнера остаётся опциональным и включается через `.env`.

## API

### GET /health

```bash
curl http://localhost:8000/health
```

Ответ:

```json
{"status":"ok"}
```

### POST /check

```bash
curl -X POST "http://localhost:8000/check" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://example.com\"}"
```

Тело запроса:

```json
{
  "url": "https://example.com"
}
```

### Markdown export

`POST /check/markdown` принимает то же тело запроса, что и `POST /check`, запускает обычную проверку и возвращает человекочитаемый отчёт в `text/markdown`.

`body.json`:

```json
{
  "url": "https://example.com"
}
```

Windows PowerShell:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/check/markdown" -H "Content-Type: application/json" --data-binary "@body.json"
```

Markdown export форматирует уже готовый `CheckResult`: он не запускает анализаторы повторно, не использует LLM и не обращается к внешним API.

## Пример структуры ответа

Ответ `POST /check` содержит основные блоки:

- `site`
- `check`
- `availability`
- `domain_compliance`
- `browser_check`
- `cookies`
- `advertising`
- `accessibility`
- `infrastructure`
- `owner_requisites`
- `forms`
- `policy`
- `external_services`
- `security`
- `risk_assessment`
- `report`

`report` имеет структуру:

```json
{
  "summary": [],
  "recommendations": [],
  "checked_areas": [],
  "manual_review_required": [],
  "limitations": [],
  "recommendation": "",
  "llm_generated": false
}
```

## Переменные окружения

| Переменная | Значение по умолчанию | Назначение |
|---|---:|---|
| `APP_NAME` | `Site Compliance Checker` | Название приложения |
| `APP_ENV` | `local` | Окружение |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `ENABLE_BROWSER_CHECK` | `false` | Включает Playwright browser check |
| `BROWSER_TIMEOUT_SECONDS` | `15` | Таймаут browser check |
| `BROWSER_NAVIGATION_WAIT_UNTIL` | `networkidle` | Условие ожидания навигации Playwright |
| `BROWSER_MAX_NETWORK_REQUESTS` | `200` | Лимит сетевых запросов в browser result |
| `ENABLE_COOKIE_INTERACTION_CHECK` | `false` | Включает cookie interaction check |
| `COOKIE_INTERACTION_TIMEOUT_SECONDS` | `10` | Таймаут cookie interaction |
| `COOKIE_INTERACTION_TEXT_LIMIT` | `3000` | Лимит текста для поиска cookie-кнопок |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Таймаут HTTP-запросов |
| `MAX_PAGES_PER_SITE` | `5` | Максимум страниц crawl |
| `MAX_REQUESTS_PER_SITE` | `15` | Максимум HTTP-запросов crawl |

## Тесты

```bash
pytest
```

или на Windows без активации окружения:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Статус MVP

Backend-MVP завершён.

Возможные следующие этапы:

- экспорт отчёта в Markdown/HTML/PDF;
- frontend;
- Telegram bot;
- MCP interface;
- история проверок;
- очередь задач и фоновые проверки;
- расширенная проверка через внешние источники.
