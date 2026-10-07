import base64
from types import SimpleNamespace

import fakeredis
import pytest
from fastapi.testclient import TestClient

from gateway.core.auth import User, UserStore, _ph, _Record
from gateway.main import create_app


@pytest.fixture
def redis():
    return fakeredis.FakeAsyncRedis()


class FakeQdrant:
    """Thay AsyncQdrantClient: `points` = {point_id: payload}; `down=True` → mọi lời gọi lỗi."""

    def __init__(self) -> None:
        self.points: dict[str, dict] = {}
        self.down = False

    def _check(self) -> None:
        if self.down:
            raise ConnectionError("qdrant down")

    async def retrieve(self, collection_name, ids, **_):
        self._check()
        return [SimpleNamespace(id=i, payload=self.points[i]) for i in ids if i in self.points]

    async def get_collections(self):
        self._check()
        return SimpleNamespace(collections=[])

    async def close(self) -> None:
        pass


@pytest.fixture
def qdrant() -> FakeQdrant:
    return FakeQdrant()


@pytest.fixture
def client(redis, qdrant):
    users = UserStore(
        {
            "m@x.test": _Record(User("u_m", "m@x.test", "member"), _ph.hash("pw-member")),
            "a@x.test": _Record(User("u_a", "a@x.test", "admin"), _ph.hash("pw-admin")),
        }
    )
    with TestClient(create_app(redis=redis, users=users, qdrant=qdrant)) as c:
        yield c


def basic(email: str, pw: str) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"{email}:{pw}".encode()).decode()}


@pytest.fixture
def member() -> dict[str, str]:
    return basic("m@x.test", "pw-member")


@pytest.fixture
def admin() -> dict[str, str]:
    return basic("a@x.test", "pw-admin")
