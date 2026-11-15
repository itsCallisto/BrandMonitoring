from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MentionCreate(BaseModel):
    brand: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1)
    url: str = Field(min_length=1, max_length=2048)
    timestamp: datetime


class MentionRead(MentionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sentiment: str | None = None
    topic: str | None = None
    urgency: str | None = None
