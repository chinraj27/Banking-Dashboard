from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import bearer, get_current_user
from app.core.config import settings
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.database.mongo import log_activity
from app.database.postgres import get_db
from app.database.redis_client import cache
from app.models import User
from app.schemas.schemas import Envelope, LoginRequest, TokenOut, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])

_DUMMY_HASH = hash_password("dummy-password-1")  # keeps login timing similar for unknown emails


@router.post("/register", response_model=Envelope[UserOut], status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, full_name=payload.full_name, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    log_activity(user.id, "user_registered")
    return {"data": user, "message": "Account created"}


@router.post("/login", response_model=Envelope[TokenOut])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == payload.email.lower())).first()
    hashed = user.hashed_password if user else _DUMMY_HASH
    valid = verify_password(payload.password, hashed)
    if not user or not valid or not user.is_active:
        log_activity(None, "login_failed", email=payload.email.lower())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token, jti = create_access_token(user.id, user.role)
    ttl = settings.access_token_minutes * 60
    cache.set(f"session:{jti}", str(user.id), ttl)  # Redis-backed session
    log_activity(user.id, "login")
    return {
        "data": {"access_token": token, "expires_in": ttl, "user": user},
        "message": "Logged in",
    }


@router.post("/logout", response_model=Envelope[dict])
def logout(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    user: User = Depends(get_current_user),
):
    cache.delete(f"session:{decode_token(creds.credentials)['jti']}")
    log_activity(user.id, "logout")
    return {"data": {}, "message": "Logged out"}


@router.get("/me", response_model=Envelope[UserOut])
def me(user: User = Depends(get_current_user)):
    return {"data": user}
