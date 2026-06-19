/**
 * AudioWorklet utilities for Gemini Live voice sessions.
 *
 * Responsibilities:
 *   - Load ``/audio-worklet-processor.js`` into an AudioContext
 *   - Wire mic → AudioWorkletNode → caller callback (as Int16Array)
 *   - Encode PCM bytes → base64 for WebSocket transmission
 *   - Decode base64 → PCM bytes for AudioContext playback
 *
 * Audio contract (matches Gemini Native Audio):
 *   - Sample rate : 24 000 Hz
 *   - Bit depth   : 16-bit signed integer (Int16Array / PCM)
 *   - Channels    : mono
 */

const TARGET_SAMPLE_RATE = 24_000

// ---------------------------------------------------------------------------
// Mic capture
// ---------------------------------------------------------------------------

export interface ResamplerHandle {
  /** Stop the mic stream and tear down the AudioContext. */
  stop: () => void
}

/**
 * Open the microphone and stream resampled 24 kHz PCM Int16 chunks to
 * ``onChunk``.
 *
 * Loads the AudioWorklet processor from ``/audio-worklet-processor.js``
 * (served from ``frontend/public/``).  This is the only place the
 * worklet module is imported.
 *
 * @throws If the user denies microphone permission or the browser does
 *   not support AudioWorklet (very rare; all modern browsers do).
 */
export async function createResampler(
  onChunk: (pcm: Int16Array) => void,
): Promise<ResamplerHandle> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })

  const ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE })

  // If the context already runs at the right rate we still go through the
  // worklet so the code path is consistent across devices.
  await ctx.audioWorklet.addModule('/audio-worklet-processor.js')

  const source = ctx.createMediaStreamSource(stream)

  const workletNode = new AudioWorkletNode(ctx, 'mic-resampler', {
    processorOptions: { inputSampleRate: ctx.sampleRate },
    numberOfInputs: 1,
    numberOfOutputs: 0,  // mic-only; no speaker output
  })

  workletNode.port.onmessage = (ev: MessageEvent<{ pcm: ArrayBuffer }>) => {
    onChunk(new Int16Array(ev.data.pcm))
  }

  source.connect(workletNode)

  return {
    stop() {
      source.disconnect()
      workletNode.port.close()
      workletNode.disconnect()
      stream.getTracks().forEach((t) => t.stop())
      void ctx.close()
    },
  }
}

// ---------------------------------------------------------------------------
// Encoding / decoding helpers
// ---------------------------------------------------------------------------

/**
 * Encode a PCM Int16Array to a base64 string for WebSocket transmission.
 *
 * The ArrayBuffer backing the Int16Array is converted to a Uint8Array
 * view and then encoded character-by-character — this avoids
 * ``btoa(String.fromCharCode(...spread))`` which fails on large arrays.
 */
export function encodePCMToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

/**
 * Decode a base64 string from the server into a Float32Array suitable
 * for ``AudioContext.createBuffer`` playback.
 *
 * The raw bytes are interpreted as 16-bit little-endian signed integers
 * and normalised to the [-1, 1] Float32 range expected by the Web Audio
 * API.
 */
export function decodePCMFromBase64(b64: string): Float32Array {
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }

  // Int16 little-endian PCM → Float32
  const sampleCount = bytes.length >> 1  // 2 bytes per sample
  const float32 = new Float32Array(sampleCount)
  const view = new DataView(bytes.buffer)
  for (let i = 0; i < sampleCount; i++) {
    float32[i] = view.getInt16(i * 2, true) / 32768
  }
  return float32
}

/**
 * Schedule playback of a Float32Array PCM chunk via the given AudioContext.
 *
 * Chunks are queued end-to-end using a rolling cursor so back-to-back calls
 * produce seamless audio without gaps or overlaps.  The cursor is stored on
 * the AudioContext instance itself so the same context can be passed on every
 * call without needing external state.
 */
export function schedulePlayback(ctx: AudioContext, pcm: Float32Array): void {
  const buffer = ctx.createBuffer(1, pcm.length, TARGET_SAMPLE_RATE)
  buffer.copyToChannel(pcm, 0)
  const source = ctx.createBufferSource()
  source.buffer = buffer
  source.connect(ctx.destination)

  // Roll the cursor forward: start right after the previous chunk ends,
  // or immediately if we're behind the playhead (first chunk / after a gap).
  const ctxWithCursor = ctx as AudioContext & { _playAt?: number }
  const startAt = Math.max(ctx.currentTime, ctxWithCursor._playAt ?? 0)
  ctxWithCursor._playAt = startAt + buffer.duration

  source.start(startAt)
}
