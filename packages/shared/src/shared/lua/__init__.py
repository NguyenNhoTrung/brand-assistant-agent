from importlib.resources import files

from redis.asyncio import Redis
from redis.commands.core import AsyncScript

from shared import redis_keys as keys


def _source(name: str) -> str:
    return (files(__package__) / f"{name}.lua").read_text()


class Scripts:
    """Đăng ký script Lua một lần lúc khởi động; gọi bằng EVALSHA."""

    def __init__(self, redis: Redis):
        self._create_job: AsyncScript = redis.register_script(_source("create_job"))

    async def create_job(
        self,
        *,
        job_id: str,
        user_id: str,
        conversation_id: str,
        idem_key: str,
        input_json: str,
        now_ms: int,
        job_type: str,
        title: str,
    ) -> tuple[bool, str]:
        created, jid = await self._create_job(
            keys=[
                keys.idem(user_id, idem_key),
                keys.job(job_id),
                keys.user_jobs(user_id),
                keys.QUEUE,
                keys.conv(conversation_id),
                keys.user_convs(user_id),
            ],
            args=[job_id, user_id, conversation_id, input_json, now_ms, job_type, title],
        )
        return bool(int(created)), jid.decode() if isinstance(jid, bytes) else str(jid)
