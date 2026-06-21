"""Gemini Live bidirectional audio session bridge.

``GeminiLiveSession`` connects a FastAPI WebSocket (browser) to the
Gemini Native Audio Live API and manages the full lifecycle:

  1. Connect to Gemini Live with function declarations and VAD config.
  2. Send ``session_started`` to the browser.
  3. Concurrently pump audio in both directions:
       browser → Gemini  (_browser_to_gemini)
       Gemini  → browser (_gemini_to_browser)
  4. On disconnect/error: collect transcript + tools, return them so the
     caller can generate a call summary and persist it.

Security: ``customer_id`` is held on this object and injected into every
tool call server-side.  It is never readable from Gemini's perspective.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from uuid import UUID

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect
from google.genai import Client as GenAiClient
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.settings import get_settings
from app.schemas.voice import VoiceEvent, VoiceEventType
from app.voice.tools import GEMINI_TOOL_DECLARATIONS, dispatch_tool

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """\
You are EVA, a warm and helpful voice assistant for CloudDesk CRM.
You are on a live phone call with a customer right now.

Customer:
  Name    : {name}
  Email   : {email}
  Company : {company}
  Plan    : {plan_tier}

CONVERSATION HISTORY (most recent first):
{recent_sessions}

LANGUAGE — STRICT:
- You may ONLY speak in English or Bangla.  No other language ever.
- Speak Bangla ONLY when the customer uses Bengali script characters
  (আ, ক, প, ব, etc.).  If you see Bengali script → respond in Bangla.
- For EVERY other language — English, Hindi, Hinglish, Arabic, French,
  Devanagari script, or anything else — ALWAYS respond in English.
  Never mirror Hindi or any non-Bengali language back to the customer.
- When in doubt, default to English.
- In Bangla, use everyday spoken Bangla (চলিত ভাষা).  Address as আপনি.
- In English, use natural spoken English with contractions (I'm, you've,
  let's, that's, don't).

SPEECH STYLE — CRITICAL:
- Talk like a real person on the phone — warm, natural, flowing sentences.
- NEVER read out raw data, bullet points, or lists.  Weave numbers and dates
  into natural sentences (e.g., "Your last invoice was $120, due on the 15th"
  not "Amount: $120. Due date: 2024-01-15").
- Use natural openers: "Sure!", "Of course!", "Great, let me check that for
  you", "So I can see here that…"
- Keep each response to 2–3 short sentences.  If more context is needed ask a
  follow-up question rather than giving a long answer all at once.

TOOLS:
- Always use the tools when the customer asks about billing, subscriptions,
  tickets, usage, or documentation.  Never guess or make up data.
- Call get_session_history if the customer implies shared context from a
  prior session — something you could not know from the current call alone.
  Ask yourself: would knowing prior session history help answer this?
  If yes, call get_session_history.

CONVERSATION FLOW:
- Stay on the call until the customer says goodbye or hangs up.
- After answering, naturally invite the next question — one brief, friendly
  prompt like "Anything else I can help with?" or, in Bangla, "আর কোনো
  সাহায্য লাগবে?"
- If the customer goes quiet for a few seconds, gently check in:
  "Still there?" or "আছেন তো?"
- NEVER end the session yourself.
"""


def _build_system_prompt(customer_context: dict) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        name=customer_context.get("name", "Valued Customer"),
        email=customer_context.get("email", "—"),
        company=customer_context.get("company", "—"),
        plan_tier=customer_context.get("plan_tier", "unknown"),
        recent_sessions=customer_context.get("recent_sessions", "No prior sessions on record."),
    )


class GeminiLiveSession:
    """Stateful bridge between one browser WebSocket and one Gemini Live session.

    A fresh instance should be created per WebSocket connection — instances
    are NOT reusable.
    """

    def __init__(
        self,
        customer_id: str | UUID,
        customer_context: dict | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._customer_id: UUID = (
            UUID(str(customer_id)) if not isinstance(customer_id, UUID) else customer_id
        )
        self._customer_context: dict = customer_context or {}
        self._session_factory = session_factory

        # Session state — populated during run()
        self._session_id: str = str(uuid.uuid4())
        self._transcript: list[dict] = []   # {"role": "user"|"assistant", "text": "..."}
        self._tools_called: list[str] = []

        # Diagnostic timing state — see _log_turn_diagnostics.
        self._diag_session_started_at: float = time.monotonic()
        self._diag_last_event_at: float | None = None
        self._diag_turn_index: int = 0

        # Playback gating: True while Gemini is generating/playing audio.
        # Browser mic audio is NOT forwarded to Gemini during this window to
        # prevent false VAD triggers. Cleared when the browser signals
        # playback_complete (PLAYBACK_COMPLETE event).
        self._gemini_speaking: bool = False

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def transcript(self) -> list[dict]:
        return list(self._transcript)

    @property
    def tools_called(self) -> list[str]:
        return list(self._tools_called)

    async def run(self, websocket: WebSocket) -> tuple[str, list[str]]:
        """Run the full voice session.

        Connects to Gemini Live, pumps audio in both directions until the
        browser disconnects or Gemini closes the session, then returns the
        accumulated transcript and tool list for call-summary generation.

        Returns
        -------
        tuple[str, list[str]]
            ``(session_id, tools_called)``
        """
        settings = get_settings()

        if settings.vertexai_enabled:
            genai_client = GenAiClient(
                vertexai=True,
                project=settings.gcp_project,
                location=settings.gcp_location,
            )
            model = settings.gemini_audio_model_vertex
        else:
            # Preview native audio models require v1alpha (not the default v1beta).
            genai_client = GenAiClient(
                api_key=settings.google_api_key,
                http_options={"api_version": "v1alpha"},
            )
            model = settings.gemini_audio_model

        system_prompt = _build_system_prompt(self._customer_context)
        live_config = _build_live_config(system_prompt)

        # Notify browser that the session is ready
        await _send_event(websocket, VoiceEvent(
            type=VoiceEventType.SESSION_STARTED,
            session_id=self._session_id,
        ))

        try:
            async with genai_client.aio.live.connect(
                model=model, config=live_config
            ) as live_session:
                await self._run_tasks(websocket, live_session)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GeminiLiveSession(%s) error: %s", self._session_id, exc)
            try:
                await _send_event(websocket, VoiceEvent(
                    type=VoiceEventType.ERROR,
                    message=str(exc),
                ))
            except Exception:  # noqa: BLE001
                pass

        # Notify browser that the session ended
        try:
            await _send_event(websocket, VoiceEvent(
                type=VoiceEventType.SESSION_ENDED,
                session_id=self._session_id,
            ))
        except Exception:  # noqa: BLE001
            pass

        return self._session_id, self._tools_called

    def _append_transcript(self, role: str, text: str) -> None:
        """Accumulate streaming transcript chunks into whole turns.

        Gemini Live streams transcription word-by-word. We merge consecutive
        chunks of the same role so the summary LLM receives clean sentences
        instead of per-syllable fragments.
        """
        if self._transcript and self._transcript[-1]["role"] == role:
            self._transcript[-1]["text"] += text
        else:
            self._transcript.append({"role": role, "text": text})

    # ── Internal concurrency ─────────────────────────────────────────────────

    async def _run_tasks(self, websocket: WebSocket, live_session: object) -> None:
        """Run both pump tasks; cancel the surviving task when one exits."""
        t_up = asyncio.create_task(
            self._browser_to_gemini(websocket, live_session),
            name=f"browser_to_gemini:{self._session_id}",
        )
        t_down = asyncio.create_task(
            self._gemini_to_browser(websocket, live_session),
            name=f"gemini_to_browser:{self._session_id}",
        )
        try:
            _done, pending = await asyncio.wait(
                [t_up, t_down],
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for task in [t_up, t_down]:
                if not task.done():
                    task.cancel()
            await asyncio.gather(t_up, t_down, return_exceptions=True)

    # ── Browser → Gemini ─────────────────────────────────────────────────────

    async def _browser_to_gemini(
        self,
        websocket: WebSocket,
        live_session: object,
    ) -> None:
        """Forward audio and control events from the browser to Gemini Live."""
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.debug("browser_to_gemini: WS closed for session %s", self._session_id)
                return

            try:
                event = VoiceEvent.model_validate_json(raw)
            except Exception as exc:  # noqa: BLE001
                logger.debug("browser_to_gemini: invalid event %s: %s", raw[:80], exc)
                continue

            if event.type == VoiceEventType.AUDIO_CHUNK and event.data:
                if self._gemini_speaking:
                    continue
                try:
                    pcm_bytes = base64.b64decode(event.data)
                    await live_session.send(
                        input=types.LiveClientRealtimeInput(
                            media_chunks=[
                                types.Blob(
                                    data=pcm_bytes,
                                    mime_type="audio/pcm;rate=24000",
                                )
                            ]
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("browser_to_gemini: send error: %s", exc)

            elif event.type == VoiceEventType.PLAYBACK_COMPLETE:
                # Browser finished playing Gemini's audio. Unmute mic so the
                # next user turn can flow through. No audio_stream_end needed —
                # the log shows Gemini fires turn_complete on its own schedule
                # (matching actual playback duration), always before this event
                # arrives. Sending audio_stream_end after turn_complete lands it
                # in the next turn's listening phase and can cut off responses.
                self._gemini_speaking = False
                logger.info(
                    "browser_to_gemini: playback_complete — mic re-armed session=%s",
                    self._session_id,
                )

            elif event.type == VoiceEventType.END_OF_AUDIO:
                # VAD handles end-of-turn detection automatically; no action needed.
                pass

            elif event.type == VoiceEventType.INTERRUPT:
                # Gemini Live detects user speech via VAD and interrupts itself.
                # We must NOT return here — returning would end the whole session.
                self._gemini_speaking = False
                logger.debug("browser_to_gemini: interrupt received for %s (VAD handles it)", self._session_id)

    # ── Gemini → Browser ─────────────────────────────────────────────────────

    async def _gemini_to_browser(
        self,
        websocket: WebSocket,
        live_session: object,
    ) -> None:
        """Forward audio, transcripts, and tool events from Gemini to the browser.

        The SDK's ``receive()`` async generator is exhausted after each model
        turn (``turn_complete``).  We loop continuously so the session stays
        alive across multiple turns — exactly like a real phone call.
        """
        try:
            while True:
                async for response in live_session.receive():
                    await self._handle_response(websocket, live_session, response)
                # receive() exhausted after turn_complete — loop for next turn.
        except Exception as exc:  # noqa: BLE001
            # Gemini closed its side (timeout, rate-limit, model error, etc.).
            # Do NOT return — that would trigger FIRST_COMPLETED in _run_tasks
            # and end the session without the user clicking End Call.
            # Instead, park here until _browser_to_gemini is cancelled (browser
            # disconnects), which is the only legitimate session-end signal.
            logger.warning("gemini_to_browser: Gemini closed — waiting for browser disconnect: %s", exc)
            await asyncio.Event().wait()  # cancelled when browser closes WS

    async def _handle_response(
        self,
        websocket: WebSocket,
        live_session: object,
        response: object,
    ) -> None:
        """Process a single Gemini Live response."""

        # ── Server content (audio + transcription) ───────────────────────
        sc = getattr(response, "server_content", None)
        self._log_turn_diagnostics(response, sc)
        if sc is not None:
            # Audio output from the model
            model_turn = getattr(sc, "model_turn", None)
            if model_turn is not None:
                parts = getattr(model_turn, "parts", None) or []
                for part in parts:
                    inline = getattr(part, "inline_data", None)
                    if inline is not None and inline.data:
                        # Mark Gemini as speaking on first audio chunk so
                        # _browser_to_gemini stops forwarding mic audio.
                        if not self._gemini_speaking:
                            self._gemini_speaking = True
                        audio_b64 = base64.b64encode(inline.data).decode()
                        await _send_event(websocket, VoiceEvent(
                            type=VoiceEventType.AUDIO_CHUNK,
                            data=audio_b64,
                        ))

            # Notify browser when Gemini finishes generating so it can start
            # its playback-completion timer and send playback_complete back.
            if getattr(sc, "generation_complete", None):
                await _send_event(websocket, VoiceEvent(
                    type=VoiceEventType.GENERATION_COMPLETE,
                ))
                # Unmute mic after a short grace period. Immediate unmute can
                # send a transient noise burst to Gemini's VAD right as its
                # playback timer starts, causing a false speech-onset detection
                # that leaves the session stuck collecting input. 250 ms is
                # enough for the hardware to settle; the drain window is still
                # 3-14 s so there is plenty of time to interrupt.
                session_ref = self
                async def _delayed_unmute() -> None:
                    await asyncio.sleep(0.25)
                    session_ref._gemini_speaking = False
                asyncio.create_task(_delayed_unmute())

            # Gemini's VAD detected user speech mid-response and cut itself off.
            # Tell the browser to cancel any queued audio immediately.
            if getattr(sc, "interrupted", None):
                self._gemini_speaking = False
                logger.info("gemini interrupted mid-turn session=%s", self._session_id)
                await _send_event(websocket, VoiceEvent(
                    type=VoiceEventType.INTERRUPTED,
                ))

            # User-speech transcription
            in_trans = getattr(sc, "input_transcription", None)
            if in_trans is not None:
                text = getattr(in_trans, "text", None)
                if text:
                    self._append_transcript("user", text)
                    await _send_event(websocket, VoiceEvent(
                        type=VoiceEventType.TRANSCRIPT,
                        role="user",
                        text=text,
                    ))

            # Model-speech transcription
            out_trans = getattr(sc, "output_transcription", None)
            if out_trans is not None:
                text = getattr(out_trans, "text", None)
                if text:
                    self._append_transcript("assistant", text)
                    await _send_event(websocket, VoiceEvent(
                        type=VoiceEventType.TRANSCRIPT,
                        role="assistant",
                        text=text,
                    ))

        # ── Tool / function calls ─────────────────────────────────────────
        tool_call = getattr(response, "tool_call", None)
        if tool_call is not None:
            function_calls = getattr(tool_call, "function_calls", None) or []
            for fc in function_calls:
                await self._handle_function_call(websocket, live_session, fc)

    def _log_turn_diagnostics(self, response: object, sc: object) -> None:
        """Temporary diagnostic logging for per-turn latency investigation.

        Logs the gap since the previous Gemini message and, when present,
        ``usage_metadata`` token counts — so latency growth can be
        correlated against prompt size growth across a long call. Only
        emits a log line for "meaningful" events (transcription text,
        turn/generation boundaries, usage metadata) to avoid flooding logs
        with one line per audio chunk.
        """
        now = time.monotonic()
        gap = now - self._diag_last_event_at if self._diag_last_event_at is not None else 0.0
        self._diag_last_event_at = now

        turn_complete = getattr(sc, "turn_complete", None) if sc is not None else None
        generation_complete = getattr(sc, "generation_complete", None) if sc is not None else None
        interrupted = getattr(sc, "interrupted", None) if sc is not None else None
        waiting_for_input = getattr(sc, "waiting_for_input", None) if sc is not None else None

        in_text = None
        out_text = None
        if sc is not None:
            in_trans = getattr(sc, "input_transcription", None)
            if in_trans is not None:
                in_text = getattr(in_trans, "text", None)
            out_trans = getattr(sc, "output_transcription", None)
            if out_trans is not None:
                out_text = getattr(out_trans, "text", None)

        usage = getattr(response, "usage_metadata", None)

        noteworthy = bool(
            in_text or out_text or turn_complete or generation_complete
            or interrupted or waiting_for_input or usage is not None
        )
        if noteworthy:
            usage_str = "none"
            if usage is not None:
                details = getattr(usage, "prompt_tokens_details", None) or []
                modality_str = ", ".join(
                    f"{getattr(d, 'modality', '?')}={getattr(d, 'token_count', '?')}"
                    for d in details
                )
                usage_str = (
                    f"prompt={getattr(usage, 'prompt_token_count', None)} "
                    f"response={getattr(usage, 'response_token_count', None)} "
                    f"thoughts={getattr(usage, 'thoughts_token_count', None)} "
                    f"total={getattr(usage, 'total_token_count', None)} "
                    f"modalities=[{modality_str}]"
                )

            logger.info(
                "voice_diag session=%s turn=%d t=%.2fs gap=%.2fs "
                "turn_complete=%s generation_complete=%s interrupted=%s "
                "waiting_for_input=%s in_trans_chars=%s out_trans_chars=%s usage(%s)",
                self._session_id,
                self._diag_turn_index,
                now - self._diag_session_started_at,
                gap,
                turn_complete,
                generation_complete,
                interrupted,
                waiting_for_input,
                len(in_text) if in_text else 0,
                len(out_text) if out_text else 0,
                usage_str,
            )

        if turn_complete:
            self._diag_turn_index += 1

    async def _handle_function_call(
        self,
        websocket: WebSocket,
        live_session: object,
        fc: object,
    ) -> None:
        """Execute one Gemini function call and send the response back."""
        tool_name: str = getattr(fc, "name", "unknown")
        fc_id: str | None = getattr(fc, "id", None)
        raw_args = getattr(fc, "args", {})
        args: dict = dict(raw_args) if raw_args else {}

        self._tools_called.append(tool_name)
        logger.info("voice tool call: %s args=%s session=%s", tool_name, args, self._session_id)

        # Notify browser — calling
        await _send_event(websocket, VoiceEvent(
            type=VoiceEventType.TOOL_CALL,
            tool_name=tool_name,
            status="calling",
        ))

        result: dict
        if self._session_factory is not None:
            result = await dispatch_tool(
                tool_name, args, self._session_factory, self._customer_id
            )
        else:
            result = {"error": "No session factory available"}

        # Send tool response to Gemini
        try:
            await live_session.send(
                input=types.LiveClientToolResponse(
                    function_responses=[
                        types.FunctionResponse(
                            id=fc_id,
                            name=tool_name,
                            response=result,
                        )
                    ]
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not send tool response for %s: %s", tool_name, exc)

        # Notify browser — done
        await _send_event(websocket, VoiceEvent(
            type=VoiceEventType.TOOL_CALL,
            tool_name=tool_name,
            status="done",
        ))


# ── Module-level helpers ─────────────────────────────────────────────────────


def _build_live_config(system_prompt: str) -> types.LiveConnectConfig:
    """Build the Gemini Live session configuration."""
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=system_prompt,
        tools=[
            types.Tool(function_declarations=GEMINI_TOOL_DECLARATIONS)
        ],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore"
                )
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                start_of_speech_sensitivity="START_SENSITIVITY_HIGH",
                end_of_speech_sensitivity="END_SENSITIVITY_HIGH",
                silence_duration_ms=500,
            )
        ),
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow(target_tokens=10000),
        ),
    )


async def _send_event(websocket: WebSocket, event: VoiceEvent) -> None:
    """Serialise and send a ``VoiceEvent`` to the browser; swallow send errors."""
    try:
        await websocket.send_text(event.model_dump_json())
    except Exception as exc:  # noqa: BLE001
        logger.debug("_send_event failed (%s): %s", event.type, exc)
