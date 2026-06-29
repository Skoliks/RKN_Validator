from pydantic import BaseModel, ConfigDict, Field


class AccessibilityIssueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: str
    page_url: str
    element: str
    evidence: str
    severity: str


class AccessibilityAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checked: bool = False
    issues_found: bool = False
    missing_lang: bool = False
    missing_alt_count: int = 0
    empty_alt_count: int = 0
    empty_links_count: int = 0
    empty_buttons_count: int = 0
    missing_input_labels_count: int = 0
    iframe_missing_title_count: int = 0
    heading_order_warnings_count: int = 0
    duplicate_ids_count: int = 0
    items: list[AccessibilityIssueItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
