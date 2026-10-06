import base64

import fakeredis
import pytest
from fastapi.testclient import TestClient

from gateway.core.auth import User, UserStore, _ph, _Record
from gateway.main import create_app


@pytest.fixture
def redis():
    return fakeredis.FakeAsyncRedis()


@pytest.fixture
def client(redis):
    users = UserStore(
        {
            "m@x.test": _Record(User("u_m", "m@x.test", "member"), _ph.hash("pw-member")),
            "a@x.test": _Record(User("u_a", "a@x.test", "admin"), _ph.hash("pw-admin")),
        }
    )
    with TestClient(create_app(redis=redis, users=users)) as c:
        yield c


def basic(email: str, pw: str) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"{email}:{pw}".encode()).decode()}


@pytest.fixture
def member() -> dict[str, str]:
    return basic("m@x.test", "pw-member")


@pytest.fixture
def admin() -> dict[str, str]:
    return basic("a@x.test", "pw-admin")
