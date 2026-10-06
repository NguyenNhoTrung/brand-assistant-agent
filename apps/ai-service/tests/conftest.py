import pytest

from ai_service.settings import settings


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Test đánh dấu `llm` gọi OpenAI thật → bỏ qua khi chưa có OPENAI_API_KEY (env hoặc .env)."""
    if settings.openai_api_key and settings.openai_api_key.get_secret_value().strip():
        return
    skip = pytest.mark.skip(reason="cần OPENAI_API_KEY")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip)
