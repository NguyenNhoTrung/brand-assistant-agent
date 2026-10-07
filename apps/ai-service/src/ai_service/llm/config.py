from functools import cache
from typing import Literal

import yaml
from pydantic import BaseModel

ModelAlias = Literal["chat-fast", "chat-default", "chat-strong", "embed"]


class ModelConfig(BaseModel):
    model: str
    timeout: float = 60
    max_tokens: int | None = None
    fallback: ModelAlias | None = None
    dims: int | None = None  # chỉ với alias embed


@cache
def load_models(path: str) -> dict[str, ModelConfig]:
    with open(path) as f:
        return {k: ModelConfig(**v) for k, v in yaml.safe_load(f).items()}
