import { Download } from 'lucide-react'
import type { AssetFile, AssetVersion } from '@/api'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Hint } from '@/components/ui/hint'
import { Mono } from '@/components/ui/mono'

const size = (bytes: number) =>
  bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

const basename = (path: string) => path.split('/').pop() ?? path

const FILE_HINTS: Record<string, string> = {
  'build.md': 'The skill wrote this account of its own run: what it made and what it cost.',
  'claims.md': 'One line per sentence in the piece that asserts something, with the source that backs it.',
  'held.md': 'What the skill needed and could not find, which is why it stopped.',
}

const fileHint = (path: string) => FILE_HINTS[basename(path)] ?? 'The asset itself, as the skill wrote it.'

function FileView({ file }: { file: AssetFile }) {
  if (file.media_type.startsWith('image/')) {
    return <img src={file.url} alt={file.path} className="max-h-[70vh] w-auto max-w-full self-start rounded-lg border border-line bg-paper" data-testid="asset-preview-image" />
  }
  if (file.media_type === 'text/html') {
    return <iframe src={file.url} title={file.path} sandbox="" className="h-[70vh] w-full rounded-lg border border-line bg-paper" data-testid="asset-preview-html" />
  }
  if (file.text !== null) {
    return (
      <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-paper p-4 font-sans text-sm text-ink" data-testid="asset-preview-text">
        {file.text}
      </pre>
    )
  }
  return null
}

export function Preview({ version }: { version: AssetVersion }) {
  const files = version.files
  const downloadAll = () => {
    for (const file of files) {
      const link = document.createElement('a')
      link.href = file.url
      link.download = basename(file.path)
      link.click()
    }
  }

  return (
    <section className="flex flex-col gap-3" data-testid="asset-preview" data-version={version.version}>
      {files.length === 0 ? (
        <Empty testId="asset-files-empty">no files yet</Empty>
      ) : (
        files.map((file) => (
          <figure key={file.path} className="flex flex-col gap-1">
            <figcaption>
              <Mono className="text-muted">{file.path}</Mono>
              <Hint text={fileHint(file.path)} />
            </figcaption>
            <FileView file={file} />
          </figure>
        ))
      )}
      {files.length > 0 && (
        <ul className="flex flex-col divide-y divide-line/50 rounded-lg border border-line bg-paper text-sm" data-testid="asset-files">
          {files.map((file) => (
            <li key={file.path} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2" data-testid="asset-file" data-path={file.path}>
              <Mono className="text-ink">{file.path}</Mono>
              <span className="text-xs text-muted">{file.media_type}</span>
              <span className="text-xs tabular-nums text-muted">{size(file.bytes)}</span>
              <a href={file.url} download={basename(file.path)} className="ml-auto text-xs text-ink underline-offset-4 hover:underline" data-testid="asset-file-download">
                Download
              </a>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={downloadAll} disabled={files.length === 0} data-testid="asset-download-all">
          <Download size={14} /> Download all
        </Button>
      </div>
    </section>
  )
}
