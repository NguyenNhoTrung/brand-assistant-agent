from shared.settings_base import BaseAppSettings


class Settings(BaseAppSettings):
    users_file: str = "data/users.yaml"
    cors_origins: list[str] = ["http://localhost:3000"]
    job_timeout_s: int = 180
    sse_block_ms: int = 15_000


settings = Settings()
