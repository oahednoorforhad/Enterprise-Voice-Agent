"""Analytics tool API endpoint — GET /api/v1/tools/analytics/usage.

All routes return ``ToolResult`` JSON so the LLM always receives a uniform
response shape.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.tools import ToolResult
from app.tools.analytics.functions import get_usage_analytics

router = APIRouter(prefix="/analytics", tags=["Analytics Tools"])


@router.get("/usage", response_model=ToolResult)
async def usage_analytics_endpoint(
    customer_id: UUID,
    metric_name: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> ToolResult:
    """Get usage analytics for a customer, optionally filtered by metric name."""
    result = await get_usage_analytics(session, customer_id, metric_name)
    return ToolResult.ok(result)
