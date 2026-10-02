from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserOut


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Admin accounts cannot be self-registered.
    role: Literal["OWNER", "ADVERTISER"] = "ADVERTISER"


class LoginRequest(BaseModel):
    # Not EmailStr: login only needs a lookup, and the seeded demo accounts use
    # the reserved ``.local`` domain which strict validation rejects.
    email: str = Field(min_length=3, max_length=255)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
