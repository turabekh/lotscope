from pydantic import BaseModel, Field


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1)
    keys: PushKeys


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1)


class VapidKeyResponse(BaseModel):
    public_key: str | None
