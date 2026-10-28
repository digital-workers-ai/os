import { fileUrl, type RecordFile } from '@/api'

export function Files({ record, files }: { record: string; files: RecordFile[] }) {
  const shown = files.filter((file) => file.kind !== 'signature')
  if (shown.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="record-files">
      {shown.map((file) => {
        const url = fileUrl(record, file.path)
        if (file.media_type.startsWith('image/'))
          return (
            <a key={file.path} href={url} target="_blank" rel="noreferrer">
              <img src={url} alt={file.path} className="size-24 rounded-md border border-line bg-paper object-cover" />
            </a>
          )
        if (file.media_type.startsWith('audio/'))
          return <audio key={file.path} controls preload="none" src={url} className="h-9 max-w-full" />
        return (
          <a
            key={file.path}
            href={url}
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink underline-offset-4 hover:underline"
          >
            {file.path}
          </a>
        )
      })}
    </div>
  )
}
