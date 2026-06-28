from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    final_url: str
    html: str


class HttpClient:
    def __init__(
        self,
        timeout: float | None = None,
        user_agent: str = "RKNValidator/0.1",
    ) -> None:
        self.timeout = timeout if timeout is not None else settings.request_timeout_seconds
        self.user_agent = user_agent

    async def get(self, url: str) -> HttpResponse:
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        ) as client:
            response = await client.get(url)

        return HttpResponse(
            status_code=response.status_code,
            final_url=str(response.url),
            html=response.text,
        )
