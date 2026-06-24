/**
 * Voice page — /app/voice
 *
 * Renders the EVA voice interface inside the split-panel app shell.
 */

import VoiceInterface from '../../components/VoiceInterface'

export function AppVoicePage() {
  return (
    <div className="flex flex-col h-full p-6 overflow-y-auto">
      <div className="max-w-3xl mx-auto w-full">
        <VoiceInterface />
      </div>
    </div>
  )
}
