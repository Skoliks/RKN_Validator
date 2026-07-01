from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.schemas.check import CheckRequest, CheckResult
from app.services.check_service import CheckService
from app.services.markdown_report_service import MarkdownReportService

router = APIRouter(prefix="/check", tags=["checks"])


def get_check_service() -> CheckService:
    return CheckService()


def get_markdown_report_service() -> MarkdownReportService:
    return MarkdownReportService()


@router.post("", response_model=CheckResult)
async def check_site(
    request: CheckRequest,
    check_service: CheckService = Depends(get_check_service),
) -> CheckResult | JSONResponse:
    result = await check_service.check(request.url)
    error_type = result.availability.error_type if result.availability else None

    if error_type in {"not_a_url", "invalid_url"}:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result.model_dump(mode="json"),
        )

    return result


@router.post("/markdown", response_class=PlainTextResponse)
async def check_site_markdown(
    request: CheckRequest,
    check_service: CheckService = Depends(get_check_service),
    markdown_report_service: MarkdownReportService = Depends(get_markdown_report_service),
) -> PlainTextResponse:
    result = await check_service.check(request.url)
    markdown = markdown_report_service.build(result)
    error_type = result.availability.error_type if result.availability else None
    status_code = (
        status.HTTP_400_BAD_REQUEST
        if error_type in {"not_a_url", "invalid_url"}
        else status.HTTP_200_OK
    )
    return PlainTextResponse(
        markdown,
        status_code=status_code,
        media_type="text/markdown; charset=utf-8",
    )
