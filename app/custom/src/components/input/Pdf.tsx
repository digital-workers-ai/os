import { useRef, useState } from 'react'
import { FileText } from 'lucide-react'
import type { Sent } from '@/api'
import { Banner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { base64 } from '@/lib/files'

const PDF = 'application/pdf'

export function Pdf({ busy, onPdf }: { busy: boolean; onPdf: (pdf: Sent) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)

  const picked = async (file: File | undefined) => {
    if (!file) return
    setError(null)
    if (file.type !== PDF) {
      setError(`${file.name} is not a PDF.`)
      return
    }
    onPdf({ name: 'document.pdf', media_type: PDF, data: await base64(file) })
  }

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={input}
        type="file"
        accept={PDF}
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          void picked(event.target.files?.[0])
          event.target.value = ''
        }}
      />
      <Button className="self-start" disabled={busy} onClick={() => input.current?.click()} data-testid="pdf-pick">
        <FileText aria-hidden />
        Choose a PDF
      </Button>
      {error && (
        <Banner tone="err" testId="pdf-error">
          {error}
        </Banner>
      )}
    </div>
  )
}
