/**
 * AudioWorkletProcessor: mic-to-24kHz resampler for Gemini Live.
 *
 * Loaded via:
 *   await audioContext.audioWorklet.addModule('/audio-worklet-processor.js')
 *
 * The browser AudioContext captures at the device's native sample rate
 * (typically 48 000 Hz or 44 100 Hz).  Gemini Native Audio expects
 * 24 000 Hz, 16-bit, mono PCM.
 *
 * This processor:
 *   1. Mixes stereo → mono (average of channels 0 and 1).
 *   2. Resamples from the native rate to 24 000 Hz using linear
 *      interpolation (adequate quality for voice, very low CPU cost).
 *   3. Converts Float32 → Int16 samples.
 *   4. Sends the Int16Array buffer to the main thread via postMessage.
 *
 * The main thread (audio-worklet.ts) base64-encodes the Int16Array
 * and sends it to the backend over the WebSocket.
 *
 * No ScriptProcessorNode is used — that API is deprecated.
 */

const TARGET_SAMPLE_RATE = 24000

class MicResamplerProcessor extends AudioWorkletProcessor {
  /**
   * @param {AudioWorkletNodeOptions} options
   *   processorOptions.inputSampleRate — the AudioContext sample rate,
   *   passed from the main thread at construction time.
   */
  constructor(options) {
    super()
    this._ratio = (options?.processorOptions?.inputSampleRate ?? 48000) / TARGET_SAMPLE_RATE
    this._remainder = 0.0
  }

  /**
   * Called by the audio engine with 128-frame input chunks.
   *
   * @param {Float32Array[][]} inputs  — inputs[0][0] = channel 0, etc.
   * @param {Float32Array[][]} _outputs — unused (mic-only processor)
   * @returns {boolean} true to keep the processor alive
   */
  process(inputs, _outputs) {
    const inputChannels = inputs[0]
    if (!inputChannels || inputChannels.length === 0) return true

    // Mix to mono
    const ch0 = inputChannels[0]
    const ch1 = inputChannels[1] ?? ch0
    const inputLength = ch0.length
    const mono = new Float32Array(inputLength)
    for (let i = 0; i < inputLength; i++) {
      mono[i] = (ch0[i] + ch1[i]) * 0.5
    }

    // Linear-interpolation resample to 24 kHz
    const outputLength = Math.floor((inputLength - this._remainder) / this._ratio) + 1
    const resampled = new Float32Array(outputLength)
    let outIdx = 0
    let srcPos = this._remainder

    while (srcPos < inputLength - 1) {
      const lo = Math.floor(srcPos)
      const hi = lo + 1
      const frac = srcPos - lo
      resampled[outIdx++] = mono[lo] + frac * (mono[hi] - mono[lo])
      srcPos += this._ratio
    }

    // Carry fractional position to next chunk
    this._remainder = srcPos - inputLength

    // Convert Float32 → Int16
    const pcm = new Int16Array(outIdx)
    for (let i = 0; i < outIdx; i++) {
      const clamped = Math.max(-1, Math.min(1, resampled[i]))
      pcm[i] = Math.round(clamped * 32767)
    }

    // Transfer buffer to main thread (zero-copy)
    this.port.postMessage({ pcm: pcm.buffer }, [pcm.buffer])
    return true
  }
}

registerProcessor('mic-resampler', MicResamplerProcessor)
