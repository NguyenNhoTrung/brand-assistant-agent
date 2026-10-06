from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    """Setting dùng chung. Mỗi app kế thừa và chỉ thêm đúng thứ nó cần
    (gateway không có OPENAI_API_KEY)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"
    log_level: str = "INFO"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "kb_chunks"
    git_sha: str = "dev"
