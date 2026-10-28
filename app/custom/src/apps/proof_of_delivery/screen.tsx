import { useLayoutEffect, useRef, useState, type PointerEvent } from 'react'
import { asApiError } from '@/api'
import type { ScreenProps } from '@/components/fields/ScreenField'
import { Button } from '@/components/ui/button'
import { base64 } from '@/lib/files'

const INK = '#1A1A1A'
const PAPER = '#FFFFFF'
const LINE_WIDTH = 2.5

export default function SignatureScreen({ name, onChange, src, upload, disabled }: ScreenProps) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)
  const [signing, setSigning] = useState(!src)
  const [inked, setInked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  const reset = () => {
    const element = canvas.current
    if (!element) return
    const ratio = window.devicePixelRatio || 1
    const { width, height } = element.getBoundingClientRect()
    element.width = Math.round(width * ratio)
    element.height = Math.round(height * ratio)
    const context = element.getContext('2d')!
    context.setTransform(ratio, 0, 0, ratio, 0, 0)
    context.fillStyle = PAPER
    context.fillRect(0, 0, width, height)
    context.strokeStyle = INK
    context.lineWidth = LINE_WIDTH
    context.lineCap = 'round'
    context.lineJoin = 'round'
    setInked(false)
  }

  useLayoutEffect(() => {
    if (signing) reset()
  }, [signing])

  const at = (event: PointerEvent<HTMLCanvasElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    return { x: event.clientX - box.left, y: event.clientY - box.top }
  }

  const down = (event: PointerEvent<HTMLCanvasElement>) => {
    if (disabled || busy) return
    drawing.current = true
    const context = event.currentTarget.getContext('2d')!
    const { x, y } = at(event)
    context.beginPath()
    context.moveTo(x, y)
    context.lineTo(x, y + 0.01)
    context.stroke()
    setInked(true)
  }

  const move = (event: PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return
    const context = event.currentTarget.getContext('2d')!
    const box = event.currentTarget.getBoundingClientRect()
    const coalesced = event.nativeEvent.getCoalescedEvents?.() ?? []
    for (const point of coalesced.length ? coalesced : [event.nativeEvent]) {
      context.lineTo(point.clientX - box.left, point.clientY - box.top)
    }
    context.stroke()
    const { x, y } = at(event)
    context.beginPath()
    context.moveTo(x, y)
  }

  const lift = () => {
    drawing.current = false
  }

  const done = async () => {
    const element = canvas.current
    if (!element) return
    setBusy(true)
    setError(null)
    try {
      const blob = await new Promise<Blob | null>((resolve) => element.toBlob(resolve, 'image/png'))
      if (!blob) throw new Error('The signature could not be turned into an image.')
      const stored = await upload({ name: `${name}.png`, media_type: 'image/png', data: await base64(blob) })
      onChange(stored.path)
      setVersion((count) => count + 1)
      setSigning(false)
    } catch (e) {
      setError(asApiError(e).detail)
    } finally {
      setBusy(false)
    }
  }

  if (!signing && src) {
    return (
      <div className="flex flex-col gap-2">
        <img
          src={version ? `${src}?v=${version}` : src}
          alt="Signature"
          className="h-44 w-full rounded-lg border border-line bg-white object-contain"
        />
        <Button size="sm" className="self-start" disabled={disabled} onClick={() => setSigning(true)}>
          Sign again
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <canvas
        ref={canvas}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={lift}
        onPointerLeave={lift}
        onPointerCancel={lift}
        style={{ touchAction: 'none' }}
        className="h-44 w-full cursor-crosshair rounded-lg border border-line bg-white"
        data-testid="signature-pad"
      />
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted">Sign with a finger inside the box.</span>
        <Button size="sm" variant="ghost" className="ml-auto" disabled={busy} onClick={reset} data-testid="signature-clear">
          Clear
        </Button>
        <Button size="sm" variant="solid" disabled={!inked || busy || disabled} onClick={done} data-testid="signature-done">
          Done
        </Button>
      </div>
      {error && <p className="text-xs text-err">{error}</p>}
    </div>
  )
}
