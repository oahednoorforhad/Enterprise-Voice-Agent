"""Knowledge API endpoints — global unstructured data search.

These endpoints wrap ``search_documentation`` and ``search_policies``
from the Knowledge tool family and return a uniform ``ToolResult`` JSON
shape so the LLM can always parse the response the same way.

Dependencies
------------
* ``get_db_session`` — provides an async SQLAlchemy session per request.
* The underlying functions handle OpenRouter embedding calls internally.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.tools import ToolResult
from app.tools.knowledge.functions import search_documentation, search_policies

router = APIRouter(prefix="/knowledge", tags=["Knowledge Tools"])


class SearchRequest(BaseModel):
    """JSON body for both knowledge-search endpoints."""

    query: str


@router.post("/documentation", response_model=ToolResult)
async def search_docs_endpoint(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResult:
    """Search the ``documentation`` vector collection.

    Returns up to 5 relevant documentation entries ranked by semantic
    similarity to the provided query.
    """
    result = await search_documentation(session, request.query)
    return ToolResult.ok(result)


@router.post("/policies", response_model=ToolResult)
async def search_policies_endpoint(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResult:
    """Search the ``policies`` vector collection.

    Returns up to 5 relevant policy entries ranked by semantic similarity
    to the provided query.
    """
    result = await search_policies(session, request.query)
    return ToolResult.ok(result)
