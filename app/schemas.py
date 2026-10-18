from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class LinkCreate(BaseModel):
    url: AnyHttpUrl
    # Optional custom code; otherwise one is generated.
    code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{3,16}$")


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    url: str
    clicks: int
    created_at: datetime
