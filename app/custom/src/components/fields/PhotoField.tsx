import { useRef, useState } from 'react'
import { Camera } from 'lucide-react'
import { asApiError, fileUrl } from '@/api'
import { Button } from '@/components/ui/button'
import { jpeg } from '@/lib/files'
import { useForm, type ControlProps } from './context'

export function PhotoField({ field, value, onChange, file, label, testId, disabled }: ControlProps) {
  const { record, files, upload } = useForm()
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const stored = files.find((entry) => entry.path === value)

  const picked = async (chosen: File | undefined) => {
    if (!chosen) return
    setBusy(true)
    setError(null)
    try {
      onChange((await upload(await jpeg(chosen, `${file}.jpg`))).path)
    } catch (e) {
      setError(asApiError(e).detail)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex items-center gap-2" data-testid={testId}>
      {record && stored && (
        <img src={fileUrl(record, stored.path)} alt={label ?? field.name} className="size-9 rounded-md object-cover" />
      )}
      <Button size="sm" disabled={disabled || busy} onClick={() => input.current?.click()} aria-label={label}>
        <Camera aria-hidden />
        {stored ? 'Retake' : 'Photo'}
      </Button>
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(event) => {
          void picked(event.target.files?.[0])
          event.target.value = ''
        }}
      />
      {error && <span className="text-xs text-err">{error}</span>}
    </div>
  )
}
