import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Undo2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  asApiError,
  attachFile,
  createRecord,
  getApp,
  hear,
  saveRecord,
  type ApiError,
  type AppDefinition,
  type Clip,
  type Created,
  type Cursor,
  type RecordFile,
  type Sent,
  type Values,
} from '@/api'
import { FormContext, type Form } from '@/components/fields/context'
import { Files } from '@/components/Files'
import { Pdf } from '@/components/input/Pdf'
import { Photo } from '@/components/input/Photo'
import { Scanner } from '@/components/input/Scanner'
import { Voice } from '@/components/input/Voice'
import { RecordForm } from '@/components/RecordForm'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Loading } from '@/components/ui/loading'
import { dropDraft, useDraft, type Draft } from '@/lib/drafts'
import { applyScan, applyUpdates, blankValues, merge, setPath, toPayload } from '@/lib/values'

interface Snapshot {
  fields: Values
  cursor: Cursor | null
  readback: string
}

function firstCursor(app: AppDefinition): Cursor | null {
  const template = app.template
  if (template?.kind === 'grid') {
    const row = template.rows?.values?.[0]
    const column = template.columns?.values?.[0]
    return row !== undefined && column !== undefined ? { row, column } : null
  }
  if (template?.kind === 'checklist') {
    const [section, items] = Object.entries(template.sections ?? {})[0] ?? []
    return section && items?.[0] ? { section, item: items[0] } : null
  }
  return null
}

const blankDraft = (app: AppDefinition): Draft => ({
  record: null,
  fields: blankValues(app),
  files: [],
  scan: null,
  cursor: firstCursor(app),
})

const withFile = (files: RecordFile[], stored: RecordFile) => [...files.filter((file) => file.path !== stored.path), stored]

const isRead = (file: RecordFile) => file.kind === 'photo' || file.kind === 'pdf'

function Editor({ app }: { app: AppDefinition }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { draft, latest, change } = useDraft(app.name, () => blankDraft(app))
  const [readback, setReadback] = useState('')
  const [undo, setUndo] = useState<Snapshot[]>([])
  const [busy, setBusy] = useState(0)
  const [error, setError] = useState<ApiError | null>(null)
  const said = useRef('')
  const creating = useRef<Promise<string> | null>(null)
  const clips = useRef<Promise<unknown>>(Promise.resolve())
  const byUtterance = app.template !== null || app.fields.some((field) => field.type === 'list')
  const taken = draft.files.some(isRead)
  const dirty = JSON.stringify(draft) !== JSON.stringify(blankDraft(app))

  const say = (text: string) => {
    said.current = text
    setReadback(text)
  }

  const work = async (task: () => Promise<void>) => {
    setBusy((count) => count + 1)
    setError(null)
    try {
      await task()
    } catch (e) {
      setError(asApiError(e))
    } finally {
      setBusy((count) => count - 1)
    }
  }

  const ensureRecord = () => {
    const known = latest.current.record
    if (known) return Promise.resolve(known)
    creating.current ??= createRecord(app.name, { files: [], scan: latest.current.scan, audio: null })
      .then((made) => {
        change((current) => ({ ...current, record: made.id, files: made.files }))
        return made.id
      })
      .finally(() => {
        creating.current = null
      })
    return creating.current
  }

  const upload = async (file: Sent) => {
    const stored = await attachFile(await ensureRecord(), file)
    change((current) => ({ ...current, files: withFile(current.files, stored) }))
    return stored
  }

  const adopt = (made: Created, again: boolean) => {
    change((current) => ({
      ...current,
      record: made.id,
      files: made.files,
      fields: merge(again ? blankValues(app) : current.fields, made.fields),
      cursor: again ? firstCursor(app) : current.cursor,
    }))
    if (made.transcript) say(made.transcript)
  }

  const read = (files: Sent[], attachable: boolean) =>
    work(async () => {
      const current = latest.current
      const again = current.files.some(isRead)
      if (attachable && current.record && !again) {
        for (const file of files) {
          const stored = await attachFile(current.record, file)
          change((next) => ({ ...next, files: withFile(next.files, stored) }))
        }
        return
      }
      adopt(await createRecord(app.name, { files, scan: current.scan, audio: null }), again)
      if (again) setUndo([])
    })

  const scanned = (code: string) =>
    change((current) => ({ ...current, scan: code, fields: applyScan(app, current.fields, code) }))

  const heard = (clip: Clip) => {
    clips.current = clips.current.then(() =>
      work(async () => {
        if (!byUtterance && !latest.current.record) {
          adopt(await createRecord(app.name, { files: [], scan: latest.current.scan, audio: clip }), false)
          return
        }
        const id = await ensureRecord()
        const answer = await hear(id, clip, latest.current.cursor)
        const before = latest.current
        setUndo((stack) => [...stack, { fields: before.fields, cursor: before.cursor, readback: said.current }])
        change((current) => ({ ...current, fields: applyUpdates(current.fields, answer.updates), cursor: answer.cursor }))
        say(answer.readback)
      }),
    )
  }

  const undoLast = () => {
    const last = undo.at(-1)
    if (!last) return
    setUndo((stack) => stack.slice(0, -1))
    change((current) => ({ ...current, fields: last.fields, cursor: last.cursor }))
    say(last.readback)
  }

  const save = () =>
    work(async () => {
      const id = await ensureRecord()
      const detail = await saveRecord(id, toPayload(app, latest.current.fields))
      dropDraft(app.name)
      queryClient.setQueryData(['record', id], detail)
      await queryClient.invalidateQueries({ queryKey: ['records', app.name] })
      navigate(`/records/${id}`, { replace: true })
    })

  const startOver = () => {
    change(() => blankDraft(app))
    setUndo([])
    say('')
  }

  const form: Form = {
    app,
    record: draft.record,
    files: draft.files,
    upload,
    set: (path, value) => change((current) => ({ ...current, fields: setPath(current.fields, path, value) as Values })),
  }

  return (
    <FormContext.Provider value={form}>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl text-ink">{app.title}</h1>
            <Link to={`/apps/${app.name}`} className="ml-auto text-sm text-ink underline-offset-4 hover:underline">
              Records
            </Link>
          </div>
          <p className="text-sm text-muted">{app.description}</p>
        </div>
        <Card className="flex flex-col gap-4">
          {app.input.map((input) => {
            if (input === 'photo')
              return <Photo key={input} taken={taken} busy={busy > 0} onPhotos={(photos) => read(photos, true)} />
            if (input === 'pdf') return <Pdf key={input} busy={busy > 0} onPdf={(pdf) => read([pdf], false)} />
            if (input === 'scan') return <Scanner key={input} onCode={scanned} />
            return (
              <div key={input} className="flex flex-col gap-3">
                <Voice onClip={heard} busy={busy > 0} />
                <div className="flex items-center gap-2">
                  <p className="min-h-5 flex-1 text-sm text-ink" aria-live="polite" data-testid="readback">
                    {readback}
                  </p>
                  <Button size="sm" variant="ghost" disabled={undo.length === 0} onClick={undoLast} data-testid="undo">
                    <Undo2 aria-hidden />
                    Undo
                  </Button>
                </div>
              </div>
            )
          })}
          {draft.record && <Files record={draft.record} files={draft.files} />}
        </Card>
        <ErrorBanner error={error} className="whitespace-pre-line" />
        <RecordForm
          values={draft.fields}
          cursor={draft.cursor}
          onCursor={(cursor) => change((current) => ({ ...current, cursor }))}
        />
        <div className="flex items-center gap-3">
          <Button variant="solid" size="lg" disabled={busy > 0} onClick={save} data-testid="save">
            Save
          </Button>
          {dirty && (
            <Button variant="ghost" onClick={startOver} data-testid="start-over">
              Start over
            </Button>
          )}
        </div>
      </div>
    </FormContext.Provider>
  )
}

export function NewRecord() {
  const { app: name = '' } = useParams()
  const app = useQuery({ queryKey: ['app', name], queryFn: () => getApp(name) })
  const state = app.isPending ? 'loading' : app.error ? 'error' : 'ready'

  return (
    <div className="flex flex-col gap-5" data-testid="new-record-view" data-state={state}>
      <ErrorBanner error={app.error && asApiError(app.error)} />
      {!app.data ? !app.error && <Loading /> : <Editor key={name} app={app.data} />}
    </div>
  )
}
