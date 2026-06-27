from pydantic import BaseModel, ConfigDict, Field


class WarningItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: str = "warning"


class PageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    final_url: str | None = None
    status_code: int | None = None
    title: str | None = None
    content_type: str | None = None
    depth: int = 0
    warnings: list[WarningItem] = Field(default_factory=list)


class PagesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_found: int = 0
    total_checked: int = 0
    items: list[PageItem] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)


class PageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    final_url: str | None = None
    status_code: int | None = None
    html: str | None = None
    text: str | None = None
    title: str | None = None
    content_type: str | None = None


class CrawlResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: list[PageData] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)
