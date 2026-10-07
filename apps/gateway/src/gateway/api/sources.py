from fastapi import APIRouter, Depends
from qdrant_client import AsyncQdrantClient

from gateway.core.auth import User, current_user
from gateway.core.errors import Problem
from gateway.core.redis import get_qdrant
from gateway.settings import settings
from shared import kb
from shared.contracts import SourceView

router = APIRouter(prefix="/v1/sources", tags=["sources"])


@router.get("/{chunk_id:path}")
async def get_source(
    chunk_id: str, _: User = Depends(current_user), qdrant: AsyncQdrantClient = Depends(get_qdrant)
) -> SourceView:
    """Nội dung chunk cho hover citation. `chunk_id` dạng `products/x.md#0` — client phải encode `#` thành `%23`."""
    try:
        points = await qdrant.retrieve(
            settings.qdrant_collection, ids=[kb.point_id(chunk_id)], with_payload=True, with_vectors=False
        )
    except Exception as e:
        raise Problem(503, "internal_error", "Không đọc được knowledge base") from e
    if not points or not points[0].payload:
        raise Problem(404, "source_not_found")
    return SourceView.model_validate(points[0].payload)
