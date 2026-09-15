import { useState } from 'react'
import { assetFileUrl, type AssetVersion, type DraftFile } from '@/api'
import { Section } from '@/components/assets/Section'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Mono } from '@/components/ui/mono'
import { compact } from '@/lib/format'

const TEXT_PATH = /\.(md|txt)$/

const isText = (file: DraftFile) =>
  file.media_type.startsWith('text/') || file.media_type === 'application/json' || TEXT_PATH.test(file.path)

function Frame({ seq, file }: { seq: number; file: DraftFile }) {
  const url = assetFileUrl(seq, file.path)
  if (file.media_type.startsWith('image/'))
    return <img src={url} alt={file.path} className="max-h-80 w-full rounded-md border border-line object-contain" />
  if (file.media_type.startsWith('video/'))
    return <video src={url} controls className="max-h-80 w-full rounded-md border border-line" />
  if (file.media_type === 'text/html')
    return <iframe src={url} title={file.path} className="h-80 w-full rounded-md border border-line bg-paper" />
  return (
    <div className="flex h-20 w-full items-center justify-center rounded-md border border-dashed border-line text-xs text-muted">
      {file.media_type}
    </div>
  )
}

export function Preview({ seq, version }: { seq: number; version: AssetVersion | null }) {
  const [copied, setCopied] = useState<string | null>(null)
  const files = version?.files ?? []
  const text = files.find(isText) ?? null

  const downloadAll = () => {
    for (const file of files) {
      const link = document.createElement('a')
      link.href = assetFileUrl(seq, file.path)
      link.download = file.path
      link.click()
    }
  }

  const copyText = async () => {
    if (!text) return
    try {
      const response = await fetch(assetFileUrl(seq, text.path))
      await navigator.clipboard.writeText(await response.text())
      setCopied('copied')
    } catch {
      setCopied('copy failed')
    }
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <Section title="Preview" testId="asset-preview">
      {files.length === 0 ? (
        <Empty>this version carries no file</Empty>
      ) : (
        <>
          <div className="space-y-2">
            {files.map((file) => (
              <Frame key={file.path} seq={seq} file={file} />
            ))}
          </div>
          <ul className="mt-3 space-y-1">
            {files.map((file) => (
              <li
                key={file.path}
                className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-xs"
                data-testid="asset-file"
                data-path={file.path}
              >
                <Mono className="min-w-0 flex-1 text-ink">{file.path}</Mono>
                <span className="whitespace-nowrap text-muted">
                  {file.media_type} · {compact(file.bytes)}B
                </span>
                <a
                  href={assetFileUrl(seq, file.path)}
                  download
                  className="whitespace-nowrap text-muted underline-offset-4 hover:text-ink hover:underline"
                >
                  Download
                </a>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" disabled={files.length === 0} onClick={downloadAll} data-testid="asset-download">
          Download all
        </Button>
        <Button size="sm" disabled={text === null} onClick={copyText} data-testid="asset-copy-text">
          {copied ?? 'Copy text'}
        </Button>
      </div>
    </Section>
  )
}
