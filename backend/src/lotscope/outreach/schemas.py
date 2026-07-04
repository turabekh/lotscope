from pydantic import BaseModel, Field


class MailMergeRequest(BaseModel):
    from_name: str = Field(min_length=1, max_length=120)
    from_contact: str = Field(min_length=1, max_length=400)
    message: str | None = Field(default=None, max_length=4000)
    min_score: int = Field(default=30, ge=1, le=100)
    vacant_only: bool = False
    zip_code: str | None = Field(default=None, max_length=10)
