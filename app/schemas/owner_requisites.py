from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OwnerRequisiteFieldType = Literal[
    "organization_name",
    "person_name",
    "inn",
    "ogrn",
    "ogrnip",
    "address",
    "phone",
    "email",
    "privacy_email",
    "unknown",
]


class OwnerRequisiteItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_type: OwnerRequisiteFieldType
    value: str
    page_url: str
    evidence: str | None = None


class OwnerRequisitesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool = False
    organization_name: str | None = None
    person_name: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    ogrnip: str | None = None
    address_found: bool = False
    phone_found: bool = False
    email_found: bool = False
    privacy_email_found: bool = False
    manual_check_required: bool = False
    items: list[OwnerRequisiteItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
