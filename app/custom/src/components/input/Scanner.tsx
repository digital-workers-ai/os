import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ScanLine, VideoOff } from 'lucide-react'
import { Banner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const WASM = '/zxing_reader.wasm'
const EVERY_MS = 300
const REPEAT_MS = 2000

interface Detector {
  detect(source: HTMLVideoElement): Promise<{ rawValue: string }[]>
}

async function detector(): Promise<Detector> {
  const Native = (window as unknown as { BarcodeDetector?: new () => Detector }).BarcodeDetector
  if (Native) return new Native()
  const { BarcodeDetector, prepareZXingModule } = await import('barcode-detector/ponyfill')
  prepareZXingModule({
    overrides: { locateFile: (path: string, prefix: string) => (path.endsWith('.wasm') ? WASM : prefix + path) },
  })
  return new BarcodeDetector()
}

export function Scanner({ onCode }: { onCode: (code: string) => void }) {
  const [on, setOn] = useState(false)
  const [typed, setTyped] = useState('')
  const [error, setError] = useState<string | null>(null)
  const video = useRef<HTMLVideoElement>(null)
  const latest = useRef(onCode)
  latest.current = onCode

  useEffect(() => {
    if (!on) return
    let stopped = false
    let stream: MediaStream | null = null
    let timer = 0
    let last = { code: '', at: -REPEAT_MS }
    const start = async () => {
      const media = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      if (stopped || !video.current) {
        media.getTracks().forEach((track) => track.stop())
        return
      }
      stream = media
      video.current.srcObject = media
      await video.current.play()
      const reader = await detector()
      const tick = async () => {
        if (stopped || !video.current) return
        const [found] = await reader.detect(video.current).catch(() => [])
        const at = performance.now()
        if (found?.rawValue) {
          if (found.rawValue !== last.code || at - last.at > REPEAT_MS) latest.current(found.rawValue)
          last = { code: found.rawValue, at }
        }
        timer = window.setTimeout(tick, EVERY_MS)
      }
      void tick()
    }
    setError(null)
    start().catch((e: Error) => stopped || setError(`The camera did not start: ${e.message}`))
    return () => {
      stopped = true
      window.clearTimeout(timer)
      stream?.getTracks().forEach((track) => track.stop())
    }
  }, [on])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const code = typed.trim()
    if (!code) return
    latest.current(code)
    setTyped('')
  }

  return (
    <div className="flex flex-col gap-3">
      <Button variant={on ? 'outline' : 'solid'} size="lg" onClick={() => setOn(!on)} data-testid="scan-start">
        {on ? <VideoOff aria-hidden /> : <ScanLine aria-hidden />}
        {on ? 'Stop the camera' : 'Scan a code'}
      </Button>
      {on && <video ref={video} muted playsInline className="aspect-video w-full rounded-lg bg-ink object-cover" />}
      <form onSubmit={submit} className="flex gap-2">
        <Input
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          placeholder="Or type the code"
          aria-label="Code"
          autoComplete="off"
          enterKeyHint="go"
          data-testid="scan-code"
        />
        <Button type="submit" disabled={!typed.trim()}>
          Use
        </Button>
      </form>
      {error && (
        <Banner tone="err" testId="scan-error">
          {error}
        </Banner>
      )}
    </div>
  )
}
