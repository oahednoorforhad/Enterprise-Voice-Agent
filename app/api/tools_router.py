"""Tools router — base APIRouter for all LLM-callable tool endpoints.

All tool routes are mounted under ``/api/v1/tools`` and return
``ToolResult`` JSON so the LLM always receives a uniform response shape.
"""

from fastapi import APIRouter

from app.api.tools_analytics import router as analytics_router
from app.api.tools_billing import router as billing_router
from app.api.tools_customer import router as customer_router
from app.api.tools_knowledge import router as knowledge_router
from app.api.tools_ticket import router as ticket_router

tools_router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])

tools_router.include_router(ticket_router)
tools_router.include_router(analytics_router)
tools_router.include_router(knowledge_router)
tools_router.include_router(customer_router)
tools_router.include_router(billing_router)
