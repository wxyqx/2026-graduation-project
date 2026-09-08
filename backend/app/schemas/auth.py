from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=72)


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    create_time: datetime | None


class TokenOut(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut
