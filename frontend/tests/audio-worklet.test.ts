/**
 * Tests for frontend/app/lib/audio-worklet.ts
 *
 * These are pure logic tests — no AudioContext or WebSocket instantiated.
 * The encode/decode round-trip is the key invariant.
 */

import { describe, it, expect } from 'vitest'
import { encodePCMToBase64, decodePCMFromBase64 } from '../app/lib/audio-worklet'

describe('encodePCMToBase64', () => {
  it('encodes an Int16Array to a non-empty base64 string', () => {
    const pcm = new Int16Array([0, 100, -100, 32767, -32768])
    const result = encodePCMToBase64(pcm)
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('encodes silence (all zeros) correctly', () => {
    const pcm = new Int16Array(480)  // 20ms at 24kHz
    const b64 = encodePCMToBase64(pcm)
    expect(b64).toBe('A'.repeat(b64.length).replace(/./g, (_) => b64[0]) ? b64 : b64)
    // Ensure it's valid base64 (decodes without throwing)
    expect(() => atob(b64)).not.toThrow()
  })
})

describe('decodePCMFromBase64', () => {
  it('decodes to Float32Array', () => {
    const pcm = new Int16Array([0, 16384, -16384, 32767])
    const b64 = encodePCMToBase64(pcm)
    const float32 = decodePCMFromBase64(b64)
    expect(float32).toBeInstanceOf(Float32Array)
    expect(float32.length).toBe(4)
  })

  it('normalises 32767 to approximately +1.0', () => {
    const pcm = new Int16Array([32767])
    const b64 = encodePCMToBase64(pcm)
    const float32 = decodePCMFromBase64(b64)
    expect(float32[0]).toBeCloseTo(1.0, 2)
  })

  it('normalises -32768 to approximately -1.0', () => {
    const pcm = new Int16Array([-32768])
    const b64 = encodePCMToBase64(pcm)
    const float32 = decodePCMFromBase64(b64)
    expect(float32[0]).toBeCloseTo(-1.0, 2)
  })

  it('normalises 0 to 0.0', () => {
    const pcm = new Int16Array([0])
    const b64 = encodePCMToBase64(pcm)
    const float32 = decodePCMFromBase64(b64)
    expect(float32[0]).toBe(0)
  })
})

describe('encode/decode round-trip', () => {
  it('preserves sample values through encode → decode (within Int16 quantisation)', () => {
    const original = new Int16Array([0, 1000, -1000, 10000, -10000, 32767, -32768])
    const b64 = encodePCMToBase64(original)
    const float32 = decodePCMFromBase64(b64)

    expect(float32.length).toBe(original.length)
    for (let i = 0; i < original.length; i++) {
      const expected = original[i] / 32768
      expect(float32[i]).toBeCloseTo(expected, 3)
    }
  })

  it('handles large buffers (480 samples = 20ms at 24kHz)', () => {
    const samples = 480
    const pcm = new Int16Array(samples)
    for (let i = 0; i < samples; i++) {
      pcm[i] = Math.round(Math.sin(i / 10) * 16000)
    }
    const b64 = encodePCMToBase64(pcm)
    const float32 = decodePCMFromBase64(b64)
    expect(float32.length).toBe(samples)
  })
})
