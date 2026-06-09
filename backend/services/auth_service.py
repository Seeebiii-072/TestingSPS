import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext

from models.user import UserRole

if not hasattr(bcrypt, "__about__"):
    class _BcryptAbout:
        __version__ = bcrypt.__version__

    bcrypt.__about__ = _BcryptAbout()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _secret_key() -> str:
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable is required for JWT operations")
    return secret_key


def _algorithm() -> str:
    return os.getenv("ALGORITHM", "HS256")


def access_token_expire_minutes() -> int:
    return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def create_access_token(user_id: uuid.UUID, role: UserRole) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=access_token_expire_minutes())
    payload = {"sub": str(user_id), "role": role.value, "exp": expires_at}
    return jwt.encode(payload, _secret_key(), algorithm=_algorithm())


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _secret_key(), algorithms=[_algorithm()])
    except JWTError as exc:
        raise ValueError("Invalid access token") from exc
