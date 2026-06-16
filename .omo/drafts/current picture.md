EVA Codebase Review — From an AI Engineering Perspective
1. Core Architecture: "Classify → Retrieve → Reason" (Not an Agent Loop)
The orchestrator is a rigid 5-stage linear pipeline with zero iteration:
Intent Analysis (LLM) → Tool Selection (deterministic) → Tool Execution (sequential) → Evidence Aggregation → Reasoning (LLM or fallback)
This is not an agent. It's a deterministic DAG. There's no ReAct loop, no Plan-and-Solve, no opportunity for the LLM to reflect on tool outputs and choose a next action. Tools are pre-selected before any execute. If get_billing_history returns nothing and search_policies has the answer, the system has no way to adapt mid-turn.
Why this matters for a voice assistant:
- Ambiguous queries ("I have a problem with my account") can't disambiguate by trying one tool, seeing the result, then trying another.
- Chained reasoning ("Find my last billing issue, then check if there's a related ticket") is impossible without multi-step tool use.
- Latency: Two sequential LLM calls per turn × ~2-3s each = 4-6s before the user hears anything. For voice, that's an eternity.
Fix: Either embrace the pipeline honestly (it's viable for well-scoped enterprise queries) or add a proper ReAct step where the reasoning engine can request additional tools based on evidence gaps.
2. Tool Execution: Sequential Anti-Pattern
# orchestrator/service.py line 161
for tool_name in tools_to_run:
    tool_func = _TOOL_FUNCTIONS.get(tool_name)
    result = await tool_func(**kwargs)
Up to 6 independent database queries run one at a time. They are all read-only — there's zero reason they can't be parallelised with asyncio.gather(). For 6 tools at ~50ms each, sequential adds 250ms of unnecessary latency. For a voice product, every millisecond counts.
3. The Fragile Tool Dispatch Chain
_build_tool_kwargs() is an if/elif chain that must be edited for every new tool:
def _build_tool_kwargs(self, tool_name, message):
    if tool_name in ("search_documentation", "search_policies"):
        return {"session": self._session, "query": message}
    if tool_name == "get_ticket_status":
        return {"session": self._session, "customer_id": ..., "ticket_id": None}
    # ... more elifs
This is the kind of code that grows to 50 lines and becomes a maintenance hazard. The _TOOL_BUILDERS registry in the evidence aggregator already solves this pattern correctly for evidence construction. Same pattern should be used for kwargs.
And _TOOL_FUNCTIONS? It's a mutable module-level dict that tests monkeypatch. This leaks between tests and isn't thread-safe.
4. RAG: Minimal Viable, Not Production-Ready
No chunking
Every document is embedded as a single vector. A 50-page policy document and a 3-line troubleshooting step get the same treatment. Long documents will drown out their own signal in cosine similarity.
No re-ranking
Pure 1 - cosine_distance is the final rank. No cross-encoder, no Cohere rerank, no reciprocal rank fusion. This means:
- False positives from semantic similarity without precision
- No way to boost exact keyword matches
- BM25/hybrid search absent entirely
No query expansion
Single query → single embedding → single search. No multi-query, no HyDE, no query decomposition.
The embedding_client makes an HTTP call per document
The seed script calls get_embedding(content) 48 times sequentially. No batching. This is slow and expensive. Gemini supports batched embedding requests.
5. Observability: Empty Stubs
app/observability/__init__.py is an empty file. Langfuse is configured in .env (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY) but no tracing exists anywhere. 
- No token counting per turn (despite making LLM calls)
- No latency breakdown per pipeline stage
- No prompt logging
- No LLM call tracing
- No error rate tracking
The request middleware in main.py logs duration, method, and path — that's it. For an AI product that needs continuous improvement based on production data, this is a gaping hole.
6. Prompt Management: Hardcoded Strings in Python Files
# intent_analyzer.py line 41
_SYSTEM_PROMPT = (
    "You are an intent analyzer for a customer support system. "
    "Classify the customer's message into one of the following intent categories:\n"
    ...
)
Both system prompts (_SYSTEM_PROMPT in intent_analyzer.py and reasoning/pipeline.py) are:
- Hardcoded — Can't update without a deploy
- Unversioned — No prompt history, no rollback
- Not measurable — No A/B testing, no prompt evaluation
- Not templated — Everything is f-string concatenation
For comparison, any serious AI product uses a prompt registry (Langfuse prompts, a DB table, or even version-controlled JSON files).
7. Memory: Simple But Fragile
The DbConversationStore stores raw turns and injects them as a flat text blob into the reasoning prompt:
--- Prior conversation ---
Turn 1:
  Customer: Why was I charged twice?
  EVA:      I've looked into your billing records...
--- End of prior conversation ---
- No summarisation — Every turn re-reads all prior turns. For long conversations, this wastes context window and degrades quality.
- No structured retrieval — There's no semantic search over past conversations. If the customer mentioned something 5 turns ago, it's in the blob, but the LLM must re-process it each time.
- Hard truncation — At 10 turns / 20 messages, it drops older context entirely. No sliding window or summarisation compression.
- No session-level state — The ConversationSession model has summary and tools_used columns, but they're never populated.
8. Testing: Solid Foundation, Missing Critical Areas
Good: 21 test files, testcontainers for real Postgres+pgvector, mocking for LLM calls.
Missing:
- No evaluation suite — app/evaluation/__init__.py is a one-line comment. The PRD promises "50 scenarios, metrics, demo UI." None exist.
- No CI/CD — No GitHub Actions / CI configuration. Tests run locally only.
- No performance tests — No p99 latency assertions for vector search or the full pipeline.
- No regression benchmarks — No test that asserts RAG results don't regress for known queries.
- Engine monkeypatching — conftest.py monkeypatches get_engine at module level. This is fragile and not thread-safe.
9. What's Genuinely Done Well
I should balance the critique:
- Separation of concerns — The 5-stage pipeline is cleanly split across files, each with a single responsibility. This is genuinely good software engineering.
- Dependency injection for LLMClient — Every component takes llm_client as a parameter. Makes unit testing trivial.
- ToolResult/ToolResult.fail() pattern — All tool errors are structured, never raw exceptions. The LLM never sees a 500.
- Hallucination guardrails — The deterministic "insufficient evidence" path is principled. Many production systems lack this.
- HNSW index — Already created in migration 2. Good forward-thinking for scale.
- Type hints everywhere — 100% of the codebase uses modern Python type annotations. This is rare and commendable.
- Migration strategy — Alembic with proper versioning, including concurrent index creation.
- Testcontainers — Real Postgres for integration tests, not mocking the database. This catches real pgvector issues.
10. Quick Hit Issues
Issue	Severity
GOOGLE_API_KEY hardcoded in .env committed to repo	🔴 Security
pgvector ORM bind_processor broken with asyncpg	🟡 Bug
Voice layer empty after Sprint 4 placeholder	🟡 Missing
settings.py has duplicate empty lines (55-56)	🟢 Nit
EMBEDDING_MODEL set to text-embedding-004 but using Gemini	🟡 Misconfig
No health check for Gemini API on startup	🟡 Resilience
No connection retry/deadline for database	🟡 Resilience
Summary
This is a solid Sprint 1 foundation — clean code, good architecture, proper testing infrastructure. The engineering quality is above average for a project at this stage.
But it's not yet a production AI system. It's a deterministic pipeline that calls an LLM twice per turn, with no observability, no evaluation, no prompt management, no caching, no fallback model, and no streaming. For a demo or MVP, this is fine. For a real enterprise voice assistant handling customer interactions, each of the gaps above will cause measurable degradation in production.
The most urgent priorities, in order:
1. Observability (Langfuse tracing + token counting) — You can't improve what you don't measure
2. Parallel tool execution — Easy win, significant latency reduction
3. RAG quality — Chunking + reranking + hybrid search
4. Prompt management — Versioned, measurable, deployable prompts
5. Evaluation suite — Without it, you're guessing whether changes improve or regress quality