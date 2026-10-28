import { useRef, useState } from 'react'
import { Camera } from 'lucide-react'
import type { Sent } from '@/api'
import { Banner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { jpeg } from '@/lib/files'

export function Photo({
  taken,
  busy,
  onPhotos,
}: {
  taken: boolean
  busy: boolean
  onPhotos: (photos: Sent[]) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)

  const picked = async (files: File[]) => {
    if (files.length === 0) return
    setError(null)
    try {
      onPhotos(await Promise.all(files.map((file, index) => jpeg(file, `photo-${index + 1}.jpg`))))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          void picked(Array.from(event.target.files ?? []))
          event.target.value = ''
        }}
      />
      {taken ? (
        <Button className="self-start" disabled={busy} onClick={() => input.current?.click()} data-testid="retake">
          <Camera aria-hidden />
          Retake
        </Button>
      ) : (
        <Button variant="solid" size="lg" disabled={busy} onClick={() => input.current?.click()} data-testid="photo-take">
          <Camera aria-hidden />
          Take a photo
        </Button>
      )}
      {error && (
        <Banner tone="err" testId="photo-error">
          {error}
        </Banner>
      )}
    </div>
  )
}
