# Draft: EVA Sprint 2 - Retrieval Layer

## Requirements (confirmed)
- **Goal**: Build the 5 Retrieval Layer Tool families (Customer, Billing, Ticket, Analytics, Knowledge).
- **Tool Architecture**: Raw Python async functions returning specific Pydantic models (stripping DB bloat).
- **Knowledge Tool**: Pure vector search (no hybrid yet).
- **Embedding Model**: OpenRouter free embedding model (`nomic-embed-text`) via HTTP/httpx client. User explicitly requested this over Google. Need to add `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` to settings. (Note: Sprint 1 seed script used Gemini, we will use OpenRouter for the runtime tools).
- **API Exposure**: Expose these tools as FastAPI HTTP endpoints (GET requests) for testing/debugging (e.g., `/api/v1/tools/customer/profile?customer_id=...`).
- **Frontend/Auth Context**: User inputs `customer_id`. The tools will take `customer_id` as a required parameter and strictly scope data access.
- **Data Limits**: List-returning tools filter data to `created_at >= NOW() - 3 months`. Knowledge retrieval uses `LIMIT 5`.
- **Response Format**: All tools return a standardized `ToolResult[T]` Pydantic model with `data: T | None`, `error: str | None`, `success: bool`.
- **Functions to Implement**:
  - Customer: `get_customer_profile()`, `get_subscription_status()`
  - Billing: `get_billing_history()`, `get_refund_history()` (filters for status='refunded')
  - Ticket: `get_support_tickets()`, `get_ticket_status(ticket_id)`
  - Analytics: `get_usage_analytics()` (raw rows for last 3 months). Explicitly included in Sprint 2 by user.
  - Knowledge: `search_documentation()`, `search_policies()` (separate functions targeting specific collections)

## Technical Decisions
- **LLM Tool Binding**: We are building the pristine Python functions first. Orchestrator LLM binding will happen in Sprint 3.
- **Pydantic Responses**: Tools will not return SQLAlchemy ORM objects. They will return strict Pydantic schemas.
- **Error Handling**: Exceptions (like "Not Found" or DB errors) must be caught within the tool and returned as `ToolResult(success=False, error="...", data=None)`.
- **Test Strategy**: TDD. We will use `pytest` with `testcontainers` (inherited from Sprint 1). Agent-Executed QA Scenarios will use `curl` against the FastAPI endpoints.

## Open Questions
- None blocking Sprint 2 planning.

## Scope Boundaries
- INCLUDE: 5 tool families, generic `ToolResult` wrapper, Vector Search, httpx OpenRouter embedding client, FastAPI GET endpoints for tools, Pytest test suite.
- EXCLUDE: LLM reasoning/orchestrator loop (Sprint 3), Hybrid Search, Voice Audio (Sprint 4), CRM Notes tool.