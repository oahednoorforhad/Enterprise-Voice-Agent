/**
 * Voice page — /voice
 *
 * Renders the EVA voice interface inside the standard app shell.
 */

import VoiceInterface from '../components/VoiceInterface'

export function VoicePage() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-3xl mx-auto">
        <VoiceInterface />
      </div>
    </div>
  )
}
