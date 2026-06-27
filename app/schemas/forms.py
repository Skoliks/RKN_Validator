from pydantic import BaseModel, ConfigDict, Field


class FormField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    field_type: str | None = None
    required: bool = False
    label: str | None = None


class FormItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form_id: str | None = None
    page_url: str
    action: str | None = None
    method: str | None = None
    fields: list[FormField] = Field(default_factory=list)


class FormsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool = False
    total: int = 0
    items: list[FormItem] = Field(default_factory=list)
