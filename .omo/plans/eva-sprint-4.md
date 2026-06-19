 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Sprint 4 Plan: Voice Experience

 Context

 Sprint 3 delivered a complete text-based reasoning engine (orchestrator, intent analysis, tool selection, evidence aggregation, reasoning pipeline, conversational memory). Sprint 4 adds the voice layer on
 top of that foundation without touching any Sprint 3 code.

 PRD Sprint 4 deliverables:
 - Gemini Audio Integration (FR-01)
 - Conversational Memory (FR-09) — already done via DbConversationStore
 - Call Summaries (FR-10)

 Core constraint: Nothing in app/orchestrator/, app/reasoning/, app/api/chat_router.py, app/api/tools_router.py, or any existing test file may be changed.

 ---
 Architecture

 Browser (voice.tsx)
   ↓ PCM audio chunks (base64 JSON over WebSocket)
   ws://localhost:8000/api/v1/voice/stream?customer_id=...
 FastAPI WebSocket (app/voice/router.py)
   ↓ client.aio.live.connect(model=..., config={tools, system_instruction})
 Gemini Live API
   ↑↓ FunctionCall → FunctionResponse (Gemini calls tools natively)
 FastAPI tool dispatcher (app/voice/session.py)
   ↓ calls existing tool functions (app/tools/*)
 PostgreSQL
   ↑ session ends → generate CallSummary → persist to ConversationSession.summary

 Key design choices:
 - The backend acts as a WebSocket proxy: browser ↔ FastAPI ↔ Gemini Live. The Google API key never leaves the server.
 - Gemini Live handles intent, tool selection, and reasoning natively through function calling — the Sprint 3 orchestrator is untouched and continues serving the text /api/v1/chat endpoint.
 - All 8 existing tool functions are reused as-is; only their Gemini function declarations are new.
 - Call summary uses the existing LLMClient.generate_structured() pattern after the session ends.
 - ConversationSession.summary and tools_used columns already exist — no DB schema migration needed.

 ---
 Files Overview

 New backend files

 ┌──────────────────────┬──────────────────────────────────────────────────────────────────┐
 │         File         │                             Purpose                              │
 ├──────────────────────┼──────────────────────────────────────────────────────────────────┤
 │ app/schemas/voice.py │ CallSummaryResult, VoiceEvent (WS message types)                 │
 ├──────────────────────┼──────────────────────────────────────────────────────────────────┤
 │ app/voice/tools.py   │ Gemini function declarations for all 8 tools                     │
 ├──────────────────────┼──────────────────────────────────────────────────────────────────┤
 │ app/voice/session.py │ GeminiLiveSession — manages live connection + tool dispatch      │
 ├──────────────────────┼──────────────────────────────────────────────────────────────────┤
 │ app/voice/summary.py │ generate_call_summary() using LLMClient.generate_structured()    │
 ├──────────────────────┼──────────────────────────────────────────────────────────────────┤
 │ app/voice/router.py  │ WS /api/v1/voice/stream + GET /api/v1/voice/summary/{session_id} │
 └──────────────────────┴──────────────────────────────────────────────────────────────────┘

 Modified backend files

 ┌────────────────────────┬─────────────────────────────────────────────────────────────────────────────┐
 │          File          │                                What changes                                 │
 ├────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
 │ app/config/settings.py │ gemini_audio_model default → "gemini-2.0-flash-live-001"                    │
 ├────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
 │ app/memory/db_store.py │ Add update_session_summary(session, session_id, summary, tools_used) method │
 ├────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
 │ app/main.py            │ Import and include_router(voice_router)                                     │
 └────────────────────────┴─────────────────────────────────────────────────────────────────────────────┘

 New frontend files

 ┌────────────────────────────────────────────┬───────────────────────────────────────────────────────┐
 │                    File                    │                        Purpose                        │
 ├────────────────────────────────────────────┼───────────────────────────────────────────────────────┤
 │ frontend/app/routes/voice.tsx              │ /voice page                                           │
 ├────────────────────────────────────────────┼───────────────────────────────────────────────────────┤
 │ frontend/app/hooks/useVoiceSession.ts      │ WebSocket + AudioContext hook                         │
 ├────────────────────────────────────────────┼───────────────────────────────────────────────────────┤
 │ frontend/app/components/VoiceInterface.tsx │ Mic button, status, transcript display, summary panel │
 └────────────────────────────────────────────┴───────────────────────────────────────────────────────┘

 Modified frontend files

 ┌─────────────────────────────────────┬────────────────────────────────────────┐
 │                File                 │              What changes              │
 ├─────────────────────────────────────┼────────────────────────────────────────┤
 │ frontend/app/router.tsx             │ Add /voice route                       │
 ├─────────────────────────────────────┼────────────────────────────────────────┤
 │ frontend/app/components/Sidebar.tsx │ Add "Voice" nav link (Mic icon)        │
 ├─────────────────────────────────────┼────────────────────────────────────────┤
 │ frontend/app/lib/api-client.ts      │ Add getCallSummary(sessionId) function │
 └─────────────────────────────────────┴────────────────────────────────────────┘

 New test files

 ┌────────────────────────────┬───────────────────────────────────────────────┐
 │            File            │                    Covers                     │
 ├────────────────────────────┼───────────────────────────────────────────────┤
 │ tests/test_call_summary.py │ generate_call_summary() with mocked LLMClient │
 ├────────────────────────────┼───────────────────────────────────────────────┤
 │ tests/test_voice_schema.py │ CallSummaryResult and VoiceEvent validation   │
 └────────────────────────────┴───────────────────────────────────────────────┘

 ---
 Implementation Order

 Build backend first (testable without frontend), then frontend.

 Step 1 — Schemas (app/schemas/voice.py)

 class VoiceEventType(str, Enum):
     AUDIO_CHUNK = "audio_chunk"
     TRANSCRIPT = "transcript"
     TOOL_CALL = "tool_call"
     SESSION_STARTED = "session_started"
     SESSION_ENDED = "session_ended"
     ERROR = "error"

 class VoiceEvent(BaseModel):
     type: VoiceEventType
     data: str | None = None       # base64 PCM for audio chunks
     text: str | None = None       # transcript text
     role: str | None = None       # "user" | "assistant"
     tool_name: str | None = None  # for tool_call events
     status: str | None = None     # "calling" | "done"
     session_id: str | None = None
     message: str | None = None    # error message

 class CallSummaryResult(BaseModel):
     session_id: str
     conversation_summary: str
     sources_used: list[str]
     reasoning_summary: str
     recommended_next_actions: list[str]

 Step 2 — Tool Declarations (app/voice/tools.py)

 Create GEMINI_TOOL_DECLARATIONS: list[dict] with one function declaration per tool, matching the parameter signatures of the existing tool functions. Customer-scoped tools (get_billing_history,
 get_customer_profile, get_subscription_status, get_support_tickets, get_ticket_status, get_usage_analytics) declare only a query or filter param — customer_id is always injected server-side from the
 WebSocket connection context, never exposed to the model.

 Knowledge tools (search_documentation, search_policies) declare a query: string param.

 Also create a dispatcher:
 async def dispatch_tool(
     tool_name: str,
     args: dict,
     session_factory: async_sessionmaker[AsyncSession],
     customer_id: str,
     user_message: str,
 ) -> dict:
     """Map a Gemini function call to the real tool function, return serializable dict."""
 Reuse existing functions from app/tools/*/functions.py. Convert Pydantic model returns to model_dump().

 Step 3 — Live Session (app/voice/session.py)

 class GeminiLiveSession:
     def __init__(
         self,
         customer_id: str,
         customer_context: dict,
         conversation_history: str,
         llm_client_api_key: str,
         session_factory: async_sessionmaker,
     ): ...

     async def run(
         self,
         websocket: WebSocket,
         db_session: AsyncSession,
     ) -> tuple[str, list[str]]:
         """Drive the full voice session. Returns (transcript, tools_called).

         Opens Gemini Live connection with:
         - system_instruction: built from customer_context + history
         - tools: GEMINI_TOOL_DECLARATIONS
         - response_modalities: ["AUDIO"]

         Runs two concurrent asyncio tasks:
         - _browser_to_gemini(): read WS audio chunks → forward to Gemini Live
         - _gemini_to_browser(): read Gemini events → handle tool calls →
           forward audio/transcripts to WS
         """

 Inside _gemini_to_browser:
 - On server_content with audio parts → emit VoiceEvent(type=AUDIO_CHUNK, data=base64(audio))
 - On server_content with text parts → emit VoiceEvent(type=TRANSCRIPT, role="assistant", text=...)
 - On server_content.tool_call → call dispatch_tool() → send LiveClientToolResponse back to Gemini → emit VoiceEvent(type=TOOL_CALL, ...)
 - On turn_complete → accumulate transcript

 Gemini Live connect call:
 from google.genai import types

 async with client.aio.live.connect(
     model=settings.gemini_audio_model,
     config=types.LiveConnectConfig(
         system_instruction=system_prompt,
         tools=[{"function_declarations": GEMINI_TOOL_DECLARATIONS}],
         response_modalities=["AUDIO"],
         speech_config=types.SpeechConfig(
             voice_config=types.VoiceConfig(
                 prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
             )
         ),
     ),
 ) as live_session:
     ...

 Step 4 — Call Summary (app/voice/summary.py)

 class _SummaryLLMResponse(BaseModel):
     conversation_summary: str
     sources_used: list[str]
     reasoning_summary: str
     recommended_next_actions: list[str]

 async def generate_call_summary(
     llm_client: LLMClient,
     transcript: str,
     tools_called: list[str],
     customer_context: dict,
 ) -> CallSummaryResult:
     """Use LLMClient.generate_structured() — same pattern as reasoning pipeline."""

 System prompt instructs the model to: summarize the conversation, list the actual data sources accessed (from tools_called), describe the reasoning chain, and suggest next actions.

 Step 5 — db_store.py addition

 async def update_session_summary(
     self,
     session: AsyncSession,
     customer_id: str,
     summary: str,
     tools_used: list[str],
 ) -> None:
     """Persist call summary to the active ConversationSession."""
     conv_session = await self.get_or_create_session(session, customer_id)
     conv_session.summary = summary
     conv_session.tools_used = {"tools": tools_used}
     conv_session.session_status = "closed"
     conv_session.ended_at = func.now()
     await session.flush()

 Step 6 — Router (app/voice/router.py)

 voice_router = APIRouter(prefix="/api/v1/voice", tags=["Voice"])

 @voice_router.websocket("/stream")
 async def voice_stream(
     websocket: WebSocket,
     customer_id: str,          # query param
     session: AsyncSession = Depends(get_db_session),
     llm: LLMClient = Depends(get_llm_client),
 ):
     await websocket.accept()
     # 1. Load customer context + history
     # 2. Emit session_started event
     # 3. Run GeminiLiveSession.run() → get transcript + tools_called
     # 4. Generate call summary (generate_call_summary())
     # 5. Persist summary via db_store.update_session_summary()
     # 6. Emit session_ended event with session_id
     # 7. Close WebSocket

 @voice_router.get("/summary/{session_id}", response_model=CallSummaryResult)
 async def get_call_summary(
     session_id: str,
     session: AsyncSession = Depends(get_db_session),
 ):
     """Retrieve stored call summary for a session."""

 Error handling: Any exception in the WebSocket handler must be caught, an ERROR event emitted to the browser, and the connection closed gracefully. Never let an unhandled exception silently kill the WS
 connection.

 Step 7 — main.py change (one line)

 from app.voice.router import voice_router
 # ...
 app.include_router(voice_router)

 Step 8 — settings.py change (one value)

 gemini_audio_model: str = "gemini-2.0-flash-live-001"

 ▎ Note: Verify this model ID against the Gemini Live API docs (https://ai.google.dev/api/live) before running — Google occasionally updates model IDs. Also update .env.example.

 Step 9 — Frontend: useVoiceSession.ts

 Hook manages:
 1. WebSocket lifecycle (ws://…/api/v1/voice/stream?customer_id=...)
 2. Microphone capture via AudioWorklet (16kHz PCM mono) → base64 → WS
 3. Output audio decode (base64 → PCM) → queue in AudioContext for playback
 4. State: status: "idle"|"connecting"|"listening"|"speaking"|"ended", transcript: Message[], summaryId: string|null

 Key audio spec: Gemini Live expects and returns 16kHz, 16-bit, mono PCM raw bytes.

 Step 10 — Frontend: VoiceInterface.tsx + voice.tsx

 - Large mic button (pulse animation when listening, waveform when speaking)
 - Real-time transcript scroll (user messages on right, EVA on left — same ChatMessage pattern)
 - Tool call badges ("Checking billing…")
 - Call summary panel revealed after session ends (fetch from /api/v1/voice/summary/{id})
 - Customer ID from the same mock constant used in chat.tsx

 Step 11 — Frontend: Router + Sidebar

 router.tsx: add { path: '/voice', component: VoicePage } entry.
 Sidebar.tsx: add a "Voice" item with Mic icon from lucide-react (already installed), between Chat and Dashboard.

 ---
 WebSocket Protocol

 Browser → Backend:
 {"type": "audio_chunk", "data": "<base64 PCM bytes>"}
 {"type": "end_of_audio"}   // optional: user released mic
 {"type": "interrupt"}      // user interrupts EVA mid-response

 Backend → Browser:
 {"type": "session_started", "session_id": "uuid"}
 {"type": "audio_chunk", "data": "<base64 PCM bytes>"}           // EVA speaking
 {"type": "transcript", "role": "user",      "text": "..."}
 {"type": "transcript", "role": "assistant", "text": "..."}
 {"type": "tool_call", "tool_name": "get_billing_history", "status": "calling"}
 {"type": "tool_call", "tool_name": "get_billing_history", "status": "done"}
 {"type": "session_ended", "session_id": "uuid", "summary_ready": true}
 {"type": "error", "message": "..."}

 ---
 What Must NOT Change

 - app/orchestrator/ — entire directory, untouched
 - app/reasoning/ — entire directory, untouched
 - app/api/chat_router.py — untouched
 - app/api/tools_router.py — untouched
 - app/tools/*/functions.py — untouched (only called, never modified)
 - All files in tests/ that currently exist
 - app/db/models.py — no schema changes; existing columns are sufficient
 - app/core/llm_client.py — untouched; reused as-is

 ---
 Verification

 1. Unit tests (no DB, no network):
   - tests/test_call_summary.py — mock LLMClient, assert CallSummaryResult fields populated
   - tests/test_voice_schema.py — assert VoiceEvent serializes/deserializes correctly
 2. Backend smoke test (with DB running):
   - GET /health still returns 200
   - GET /ready still returns 200
   - POST /api/v1/chat still works with a text message
 3. Voice integration test (manual, browser):
   - Open http://localhost:3001/voice
   - Grant mic permission
   - Say: "Hello" → EVA greets
   - Say: "Why was I charged twice last month?" → EVA calls get_billing_history, responds
   - End call → call summary panel appears with 4 sections
 4. Run full test suite — uv run pytest — all existing tests must still pass
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌