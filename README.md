# Site Compliance Checker

MVP backend-сервис для первичной технической проверки сайтов на признаки потенциальных правовых рисков.

Сервис не выполняет юридическую экспертизу и не устанавливает факт нарушения законодательства. Он выявляет технические и документные признаки потенциального риска на проверенных страницах сайта, после чего рекомендуется ручная проверка.

## Границы MVP

В MVP реализована синхронная проверка одного сайта через HTTP API:

- нормализация URL;
- проверка доступности сайта;
- ограниченный обход страниц;
- анализ форм, согласий, политики, внешних сервисов, HTTPS, cookie-признаков, иностранных провайдеров авторизации и признаков ориентации на российских пользователей;
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

`BrowserClient` собирает cookies после загрузки страницы, сетевые запросы, видимый текст страницы и ошибки консоли. `CookieAnalyzer` использует эти данные для предварительного выявления признаков cookie-баннера, cookies после первичной загрузки до явного выбора пользователя и сторонних запросов. Проверка остаётся предварительной: сервис не делает юридический вывод, не кликает по баннерам, не отправляет формы и не делает скриншоты.

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
