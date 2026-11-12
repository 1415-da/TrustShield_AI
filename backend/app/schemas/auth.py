from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UTCDatetime


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class RegisterRequest(BaseModel):
    # Plain pattern rather than EmailStr: email-validator rejects reserved TLDs such as .test used by the demo.
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", max_length=255)
    password: str = Field(min_length=10, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    department: str = Field(default="General Operations", max_length=120)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class OrganizationRef(BaseModel):
    id: int
    name: str
    slug: str
    is_demo: bool = False


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    department: str
    title: str
    is_active: bool
    role_keys: list[str]
    primary_role: str
    permissions: list[str]
    created_at: UTCDatetime
    last_login_at: UTCDatetime | None = None
    organization: OrganizationRef | None = None

    @classmethod
    def of(cls, user) -> "UserOut":  # type: ignore[no-untyped-def]
        return cls.model_validate({**{c: getattr(user, c) for c in (
            "id", "email", "full_name", "department", "title", "is_active", "role_keys", "primary_role", "created_at",
            "last_login_at")}, "permissions": sorted(user.permissions),
            "organization": {"id": o.id, "name": o.name, "slug": o.slug, "is_demo": bool(o.is_demo)} if (o := user.organization) else None})


class LoginResponse(TokenPair):
    user: UserOut
