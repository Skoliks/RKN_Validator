from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.routes.checks import get_check_service
from app.main import app
from app.schemas.availability import AvailabilityInfo
from app.schemas.check import CheckMeta, CheckResult
from app.schemas.pages import PageItem, PagesResult
from app.schemas.report import ReportResult
from app.schemas.risk import RiskAssessment
from app.schemas.site import SiteInfo


class FakeCheckService:
    def __init__(self, result: CheckResult) -> None:
        self.result = result

    async def check(self, url: str) -> CheckResult:
        return self.result


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def make_result(
    status: str = "completed",
    available: bool = True,
    error_type: str | None = None,
    message: str | None = None,
) -> CheckResult:
    return CheckResult(
        site=SiteInfo(
            original_input="example.ru",
            normalized_url="https://example.ru",
            final_url="https://example.ru",
            domain="example.ru",
            domain_zone="ru",
        ),
        check=CheckMeta(
            status=status,
            checked_at=datetime.now(UTC),
            duration_ms=100,
            mode="sync",
            interface="api",
        ),
        availability=AvailabilityInfo(
            available=available,
            status_code=200 if available else None,
            error_type=error_type,
            message=message,
        ),
        pages=PagesResult(
            total_found=1,
            total_checked=1,
            items=[PageItem(url="https://example.ru", status_code=200)],
        )
        if status != "failed"
        else None,
        risk_assessment=RiskAssessment(total_score=0, level="low")
        if status != "failed"
        else None,
        report=ReportResult(
            summary=[message or "???????? ?????????."],
            recommendations=["????????????? ???????????? ????????? ????????."],
            recommendation="????????????? ???????????? ????????? ????????.",
            checked_areas=["??????????? ?????"],
            manual_review_required=[],
            limitations=["?????????????? ???????? ?? ???????? ??????????? ???????????."],
            llm_generated=False,
        ),
    )


def override_check_service(result: CheckResult) -> None:
    app.dependency_overrides[get_check_service] = lambda: FakeCheckService(result)


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_check_endpoint_with_valid_url() -> None:
    override_check_service(make_result())

    with TestClient(app) as client:
        response = client.post("/check", json={"url": "example.ru"})

    assert response.status_code == 200
    assert response.json()["check"]["status"] == "completed"


def test_check_endpoint_with_plain_text_returns_400() -> None:
    override_check_service(
        make_result(
            status="failed",
            available=False,
            error_type="not_a_url",
            message="Не понял ваш запрос, пожалуйста отправьте ссылку на сайт для проверки.",
        )
    )

    with TestClient(app) as client:
        response = client.post("/check", json={"url": "какая сегодня погода"})

    assert response.status_code == 400
    assert response.json()["availability"]["error_type"] == "not_a_url"


def test_check_endpoint_with_invalid_url_returns_400() -> None:
    override_check_service(
        make_result(
            status="failed",
            available=False,
            error_type="invalid_url",
            message="Ссылка указана некорректно, пожалуйста отправьте адрес сайта в формате https://example.ru.",
        )
    )

    with TestClient(app) as client:
        response = client.post("/check", json={"url": "https://"})

    assert response.status_code == 400
    assert response.json()["availability"]["error_type"] == "invalid_url"


def test_check_endpoint_with_unavailable_site_returns_200() -> None:
    override_check_service(
        make_result(
            status="failed",
            available=False,
            error_type="site_unavailable",
            message="Сайт недоступен, поэтому проверку выполнить не удалось.",
        )
    )

    with TestClient(app) as client:
        response = client.post("/check", json={"url": "example.ru"})

    assert response.status_code == 200
    assert response.json()["check"]["status"] == "failed"
    assert response.json()["availability"]["error_type"] == "site_unavailable"


def test_check_endpoint_with_empty_body_returns_422() -> None:
    with TestClient(app) as client:
        response = client.post("/check", json={})

    assert response.status_code == 422


def test_openapi_contains_check_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/check" in response.json()["paths"]
    assert "post" in response.json()["paths"]["/check"]
