import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Mic } from 'lucide-react'
import type { Clip } from '@/api'
import { Banner } from '@/components/ui/banner'
import { base64 } from '@/lib/files'
import { cn } from '@/lib/utils'

const WEBM = 'audio/webm;codecs=opus'
const MP4 = 'audio/mp4'
const HOLD_KEYS = new Set([' ', 'Enter'])

export function Voice({ onClip, busy }: { onClip: (clip: Clip) => void; busy: boolean }) {
  const [pressed, setPressed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const held = useRef(false)
  const stream = useRef<MediaStream | null>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const latest = useRef(onClip)
  latest.current = onClip

  useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), [])

  const record = async () => {
    stream.current ??= await navigator.mediaDevices.getUserMedia({ audio: true })
    if (!held.current) return
    const mimeType = MediaRecorder.isTypeSupported(WEBM) ? WEBM : MP4
    const next = new MediaRecorder(stream.current, { mimeType })
    const chunks: Blob[] = []
    next.ondataavailable = (event) => {
      if (event.data.size) chunks.push(event.data)
    }
    next.onstop = async () => {
      const type = next.mimeType || mimeType
      const blob = new Blob(chunks, { type })
      if (blob.size) latest.current({ media_type: type.split(';')[0], data: await base64(blob) })
    }
    next.start()
    recorder.current = next
  }

  const start = () => {
    if (held.current) return
    held.current = true
    setPressed(true)
    setError(null)
    record().catch((e: Error) => {
      held.current = false
      setPressed(false)
      setError(`The microphone did not start: ${e.message}`)
    })
  }

  const stop = () => {
    if (!held.current) return
    held.current = false
    setPressed(false)
    recorder.current?.stop()
    recorder.current = null
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        aria-pressed={pressed}
        onPointerDown={start}
        onPointerUp={stop}
        onPointerLeave={stop}
        onPointerCancel={stop}
        onKeyDown={(event: KeyboardEvent) => {
          if (!HOLD_KEYS.has(event.key) || event.repeat) return
          event.preventDefault()
          start()
        }}
        onKeyUp={(event: KeyboardEvent) => HOLD_KEYS.has(event.key) && stop()}
        onContextMenu={(event) => event.preventDefault()}
        className={cn(
          'flex size-28 touch-none select-none flex-col items-center justify-center gap-1 rounded-full border-2 text-sm font-medium transition-colors [-webkit-touch-callout:none]',
          pressed ? 'border-brand bg-brand text-paper' : 'border-ink bg-paper text-ink',
        )}
        data-testid="talk"
      >
        <Mic className="size-6" aria-hidden />
        {pressed ? 'Listening' : 'Hold to talk'}
      </button>
      {busy && <span className="text-xs text-muted">Working on the last clip…</span>}
      {error && (
        <Banner tone="err" testId="voice-error">
          {error}
        </Banner>
      )}
    </div>
  )
}
