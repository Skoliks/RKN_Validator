import pytest

from app.analyzers.accessibility_analyzer import AccessibilityAnalyzer
from app.schemas.accessibility import AccessibilityAnalysisResult, AccessibilityIssueItem
from app.schemas.pages import CrawlResult, PageData
from app.services.check_service import CheckService
from app.services.report_service import ReportService
from app.services.risk_service import RiskService
from tests.test_check_service import FakeAvailabilityService, FakeBrowserCheckService, FakeCrawlService, make_available
from tests.test_report_service import make_check_result
from tests.test_risk_service import factor_codes, make_check


def page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def issue(issue_type: str, severity: str = "medium", evidence: str = "evidence") -> AccessibilityIssueItem:
    return AccessibilityIssueItem(
        issue_type=issue_type,
        page_url="https://example.ru",
        element="div",
        evidence=evidence,
        severity=severity,
    )


def test_accessibility_analyzer_detects_missing_html_lang() -> None:
    result = AccessibilityAnalyzer().analyze([page("<html><body></body></html>")])

    assert result.checked is True
    assert result.missing_lang is True
    assert "missing_html_lang" in {item.issue_type for item in result.items}


def test_accessibility_analyzer_detects_image_without_alt() -> None:
    result = AccessibilityAnalyzer().analyze([page('<html lang="ru"><img src="/logo.png"></html>')])

    assert result.missing_alt_count == 1
    assert "missing_image_alt" in {item.issue_type for item in result.items}


def test_accessibility_analyzer_shortens_inline_data_image_evidence() -> None:
    result = AccessibilityAnalyzer().analyze(
        [
            page(
                '<html lang="ru"><img src="data:image/png;base64,AAAAABBBBBCCCCCDDDDDEEEEEFFFFF"></html>'
            )
        ]
    )

    item = next(item for item in result.items if item.issue_type == "missing_image_alt")
    assert item.evidence == "inline data image"
    assert "base64" not in item.evidence
    assert "AAAAA" not in item.evidence


def test_accessibility_analyzer_detects_empty_image_alt_as_low() -> None:
    result = AccessibilityAnalyzer().analyze([page('<html lang="ru"><img src="/decor.png" alt=""></html>')])

    assert result.empty_alt_count == 1
    item = next(item for item in result.items if item.issue_type == "empty_image_alt")
    assert item.severity == "low"


def test_accessibility_analyzer_detects_empty_link() -> None:
    result = AccessibilityAnalyzer().analyze([page('<html lang="ru"><a href="/next"></a></html>')])

    assert result.empty_links_count == 1


def test_accessibility_analyzer_skips_link_with_aria_label() -> None:
    result = AccessibilityAnalyzer().analyze(
        [page('<html lang="ru"><a href="/next" aria-label="Далее"></a></html>')]
    )

    assert result.empty_links_count == 0


def test_accessibility_analyzer_detects_empty_button() -> None:
    result = AccessibilityAnalyzer().analyze([page('<html lang="ru"><button></button></html>')])

    assert result.empty_buttons_count == 1


def test_accessibility_analyzer_skips_button_with_aria_label() -> None:
    result = AccessibilityAnalyzer().analyze(
        [page('<html lang="ru"><button aria-label="Закрыть"></button></html>')]
    )

    assert result.empty_buttons_count == 0


def test_accessibility_analyzer_detects_input_without_label() -> None:
    result = AccessibilityAnalyzer().analyze([page('<html lang="ru"><input name="email"></html>')])

    assert result.missing_input_labels_count == 1


def test_accessibility_analyzer_skips_input_with_placeholder() -> None:
    result = AccessibilityAnalyzer().analyze(
        [page('<html lang="ru"><input name="email" placeholder="Email"></html>')]
    )

    assert result.missing_input_labels_count == 0


def test_accessibility_analyzer_detects_iframe_without_title() -> None:
    result = AccessibilityAnalyzer().analyze(
        [page('<html lang="ru"><iframe src="https://example.com/embed"></iframe></html>')]
    )

    assert result.iframe_missing_title_count == 1


def test_accessibility_analyzer_detects_heading_skip() -> None:
    result = AccessibilityAnalyzer().analyze([page('<html lang="ru"><h1>A</h1><h3>B</h3></html>')])

    assert result.heading_order_warnings_count == 1


def test_accessibility_analyzer_detects_duplicate_id() -> None:
    result = AccessibilityAnalyzer().analyze(
        [page('<html lang="ru"><div id="same"></div><span id="same"></span></html>')]
    )

    assert result.duplicate_ids_count == 1


def test_accessibility_analyzer_limits_items_to_100() -> None:
    html = '<html lang="ru">' + "".join(f'<img src="/{index}.png">' for index in range(101)) + "</html>"
    result = AccessibilityAnalyzer().analyze([page(html)])

    assert result.missing_alt_count == 101
    assert len(result.items) == 100
    assert "Список замечаний ограничен первыми 100 элементами." in result.warnings


def test_risk_service_adds_accessibility_medium_factor() -> None:
    result = RiskService().assess(
        accessibility=AccessibilityAnalysisResult(
            checked=True,
            issues_found=True,
            missing_alt_count=1,
            items=[issue("missing_image_alt", severity="medium", evidence="/logo.png")],
        ),
        check=make_check(),
    )

    assert "accessibility_medium_issues_detected" in factor_codes(result)


def test_risk_service_adds_accessibility_low_factor_for_low_only() -> None:
    result = RiskService().assess(
        accessibility=AccessibilityAnalysisResult(
            checked=True,
            issues_found=True,
            empty_alt_count=1,
            items=[issue("empty_image_alt", severity="low", evidence="/decor.png")],
        ),
        check=make_check(),
    )

    assert "accessibility_low_issues_detected" in factor_codes(result)
    assert "accessibility_medium_issues_detected" not in factor_codes(result)


def test_risk_service_skips_accessibility_factors_when_no_issues() -> None:
    result = RiskService().assess(
        accessibility=AccessibilityAnalysisResult(checked=True, issues_found=False),
        check=make_check(),
    )

    assert {
        "accessibility_medium_issues_detected",
        "accessibility_low_issues_detected",
    }.isdisjoint(factor_codes(result))


def test_report_service_mentions_accessibility_cautiously() -> None:
    report = ReportService().build(
        make_check_result(
            risk_level="medium",
            risk_score=20,
            accessibility=AccessibilityAnalysisResult(
                checked=True,
                issues_found=True,
                missing_alt_count=1,
                empty_links_count=1,
                missing_input_labels_count=1,
                items=[
                    issue("missing_image_alt", severity="medium", evidence="/logo.png"),
                    issue("empty_link_text", severity="medium", evidence="/next"),
                    issue("missing_input_label", severity="medium", evidence="email"),
                ],
            ),
        )
    )

    assert "Обнаружены признаки возможных технических проблем доступности" in report.summary
    assert "На проверенных страницах найдены изображения без атрибута alt." in report.summary
    assert "Найдены ссылки или кнопки без доступного текстового описания." in report.summary
    assert "Найдены поля форм без автоматически определённой подписи." in report.summary
    assert "сайт не соответствует ГОСТ" not in report.summary
    assert "сайт нарушает требования доступности" not in report.summary


@pytest.mark.asyncio
async def test_check_service_includes_accessibility_result() -> None:
    service = CheckService(
        availability_service=FakeAvailabilityService(make_available()),
        crawl_service=FakeCrawlService(
            CrawlResult(pages=[page('<html><body><img src="/logo.png"></body></html>')])
        ),
        browser_check_service=FakeBrowserCheckService(enabled=False),
    )

    result = await service.check("https://example.ru")

    assert result.accessibility is not None
    assert result.accessibility.checked is True
    assert result.accessibility.issues_found is True
    assert result.accessibility.missing_alt_count == 1
