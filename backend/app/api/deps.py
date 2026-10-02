"""Shared FastAPI dependencies: DB session and authentication."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.models import User, UserRole

DbSession = Annotated[Session, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


def get_user_from_token(db: Session, token: str | None) -> User | None:
    """Resolve a JWT to a user; used by HTTP routes and WebSockets."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    return db.get(User, user_id)


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    user = get_user_from_token(db, credentials.credentials if credentials else None)
    if user is None:
        raise AuthenticationError("Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    """The signed-in user if a valid token was sent, else ``None`` (public endpoints)."""
    return get_user_from_token(db, credentials.credentials if credentials else None)


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    def _checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError(
                f"This action requires role: {', '.join(r.value for r in roles)}"
            )
        return user

    return _checker


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
OwnerUser = Annotated[User, Depends(require_roles(UserRole.OWNER))]
AdvertiserUser = Annotated[User, Depends(require_roles(UserRole.ADVERTISER))]
