import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.postgres import get_db
from app.database.redis_client import cache
from app.models import User

bearer = HTTPBearer(auto_error=False)

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Authentication middleware: verifies the JWT, checks the Redis session, loads the user."""
    if creds is None:
        raise UNAUTHORIZED
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise UNAUTHORIZED from None
    if cache.get(f"session:{payload.get('jti')}") is None:  # logged out or expired session
        raise UNAUTHORIZED
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise UNAUTHORIZED
    return user


def require_role(*roles: str):
    """Role-based access control dependency."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this resource")
        return user

    return checker
