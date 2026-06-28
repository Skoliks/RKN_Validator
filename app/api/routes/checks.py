from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.schemas.check import CheckRequest, CheckResult
from app.services.check_service import CheckService

router = APIRouter(prefix="/check", tags=["checks"])


def get_check_service() -> CheckService:
    return CheckService()


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
