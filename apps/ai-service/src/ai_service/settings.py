from pydantic import SecretStr

from shared.settings_base import BaseAppSettings


class Settings(BaseAppSettings):
    openai_api_key: SecretStr | None = None  # bắt buộc khi chạy worker/ingest — kiểm tra lúc khởi động
    models_file: str = "config/models.yaml"
    worker_concurrency: int = 4
    job_timeout_s: int = 180
    shutdown_grace_s: int = 25  # SIGTERM → chờ job đang chạy rồi cắt; < stop_grace_period 30s của compose
    checkpoint_ttl_min: int = 43_200  # AsyncRedisSaver tính TTL theo PHÚT — 30 ngày như conversation
    kb_dir: str = "data/knowledge"  # job `ingest` đọc từ đây (tương đối với thư mục chạy)
    trace_payloads: bool = True

    def require_openai_key(self) -> SecretStr:
        if self.openai_api_key is None or not self.openai_api_key.get_secret_value().strip():
            raise RuntimeError("Thiếu OPENAI_API_KEY — đặt trong .env (xem .env.example)")
        return self.openai_api_key


settings = Settings()
