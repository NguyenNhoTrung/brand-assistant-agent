import hashlib
import os
from dataclasses import dataclass
from typing import Literal

import structlog
import yaml
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cachetools import TTLCache
from fastapi import Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from gateway.core.errors import Problem

log = structlog.get_logger()
_ph = PasswordHasher()
security = HTTPBasic(auto_error=False)


@dataclass(frozen=True)
class User:
    id: str
    email: str
    role: Literal["member", "admin"]


@dataclass(frozen=True)
class _Record:
    user: User
    password_hash: str


class UserStore:
    """Đọc users.yaml, hash mật khẩu (từ env) bằng argon2id lúc khởi động."""

    def __init__(self, records: dict[str, _Record]):
        self._by_email = records
        self._verified: TTLCache[str, User] = TTLCache(maxsize=256, ttl=300)

    @classmethod
    def from_file(cls, path: str) -> "UserStore":
        with open(path) as f:
            raw = yaml.safe_load(f)["users"]
        records = {}
        for u in raw:
            password = os.environ.get(u["password_env"], "").strip()
            if not password:
                log.warning("auth.user_disabled", email=u["email"], reason=f"thiếu biến môi trường {u['password_env']}")
                continue
            user = User(id=u["id"], email=u["email"], role=u["role"])
            records[user.email] = _Record(user, _ph.hash(password))
        if not records:
            envs = ", ".join(u["password_env"] for u in raw)
            raise RuntimeError(f"Không user nào đăng nhập được — đặt {envs} trong .env ({path})")
        return cls(records)

    def verify(self, email: str, password: str) -> User | None:
        key = hashlib.sha256(f"{email}:{password}".encode()).hexdigest()
        if (cached := self._verified.get(key)) is not None:
            return cached
        rec = self._by_email.get(email)
        if rec is None:
            return None
        try:
            _ph.verify(rec.password_hash, password)
        except VerifyMismatchError:
            return None
        self._verified[key] = rec.user
        return rec.user


async def current_user(request: Request, creds: HTTPBasicCredentials | None = Depends(security)) -> User:
    if creds is None:
        raise Problem(401, "auth_required")
    store: UserStore = request.app.state.users
    user = store.verify(creds.username, creds.password)
    if user is None:
        raise Problem(401, "auth_invalid")
    structlog.contextvars.bind_contextvars(user_id=user.id)
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise Problem(403, "forbidden")
    return user
