from pydantic import SecretStr

from shared.settings_base import BaseAppSettings


class Settings(BaseAppSettings):
    openai_api_key: SecretStr | None = None  # bắt buộc khi chạy worker/ingest — kiểm tra lúc khởi động
    models_file: str = "config/models.yaml"
    worker_concurrency: int = 4
    job_timeout_s: int = 180
    trace_payloads: bool = True

    def require_openai_key(self) -> SecretStr:
        if self.openai_api_key is None or not self.openai_api_key.get_secret_value().strip():
            raise RuntimeError("Thiếu OPENAI_API_KEY — đặt trong .env (xem .env.example)")
        return self.openai_api_key


settings = Settings()
