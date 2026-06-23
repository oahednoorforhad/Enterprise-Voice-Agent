import { Loader2 } from 'lucide-react'

interface LoadingSpinnerProps {
  size?: number
  message?: string
  fullPage?: boolean
}

export default function LoadingSpinner({
  size = 24,
  message = 'Loading...',
  fullPage = false,
}: LoadingSpinnerProps) {
  const content = (
    <div className="flex flex-col items-center justify-center gap-3">
      <Loader2
        size={size}
        className="animate-spin text-brand-coral"
      />
      {message && (
        <p className="text-caption text-muted-slate">{message}</p>
      )}
    </div>
  )

  if (fullPage) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">{content}</div>
    )
  }

  return content
}
