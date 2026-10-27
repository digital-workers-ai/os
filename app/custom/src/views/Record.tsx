import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  asApiError,
  attachFile,
  getApp,
  getRecord,
  removeRecord,
  saveRecord,
  type AppDefinition,
  type Cursor,
  type Detail,
  type RecordFile,
  type Sent,
  type Values,
} from '@/api'
import { FormContext, type Form } from '@/components/fields/context'
import { Files } from '@/components/Files'
import { RecordForm } from '@/components/RecordForm'
import { Banner, ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Loading } from '@/components/ui/loading'
import { consoleUrl } from '@/lib/console'
import { stamp } from '@/lib/format'
import { blankValues, humanize, merge, setPath, toPayload } from '@/lib/values'

const NOT_COUNTED = 'Saved. Counts in the numbers after the next Rebuild'

function Standing({ detail }: { detail: Detail }) {
  if (detail.removed)
    return <Banner testId="record-removed">Removed. The next Rebuild drops what it became; the history stays.</Banner>
  if (!detail.history.some((entry) => entry.action === 'save'))
    return <p className="text-sm text-muted" data-testid="record-unsaved">Not saved yet.</p>
  if (!detail.counted)
    return (
      <p className="text-sm text-muted" data-testid="record-not-counted">
        {NOT_COUNTED}
      </p>
    )
  return (
    <p className="text-sm text-muted" data-testid="record-counted">
      {detail.entity ? (
        <>
          In the numbers as{' '}
          <a
            href={consoleUrl(`/entities/canonical?entity=${encodeURIComponent(detail.entity.id)}`)}
            target="_blank"
            rel="noreferrer"
            className="text-ink underline underline-offset-4"
          >
            {detail.entity.type.replace(/_/g, ' ')} {detail.entity.id}
          </a>
        </>
      ) : (
        'Counted in the numbers by the last Rebuild.'
      )}
    </p>
  )
}

function History({ detail }: { detail: Detail }) {
  return (
    <div className="flex flex-col gap-2" data-testid="record-history">
      <h2 className="text-sm font-medium text-muted">History</h2>
      <ol className="flex flex-col gap-1 text-sm text-ink">
        {detail.history.map((entry, index) => (
          <li key={index} className="flex gap-3">
            <span className="w-16">{humanize(entry.action)}</span>
            <span className="text-muted">{entry.actor}</span>
            <span className="ml-auto tabular-nums text-muted">{stamp(entry.at)}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function Editor({ detail, app }: { detail: Detail; app: AppDefinition }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [values, setValues] = useState<Values>(() => merge(blankValues(app), detail.fields))
  const [files, setFiles] = useState<RecordFile[]>(detail.files)
  const [cursor, setCursor] = useState<Cursor | null>(null)
  const [confirming, setConfirming] = useState(false)

  const save = useMutation({
    mutationFn: () => saveRecord(detail.id, toPayload(app, values)),
    onSuccess: (next) => {
      queryClient.setQueryData(['record', detail.id], next)
      return queryClient.invalidateQueries({ queryKey: ['records', app.name] })
    },
  })
  const remove = useMutation({
    mutationFn: () => removeRecord(detail.id),
    onSuccess: async () => {
      queryClient.setQueryData(['record', detail.id], { ...detail, removed: true })
      await queryClient.invalidateQueries({ queryKey: ['records', app.name] })
      navigate(`/apps/${app.name}`)
    },
  })

  const upload = async (file: Sent) => {
    const stored = await attachFile(detail.id, file)
    setFiles((current) => [...current.filter((entry) => entry.path !== stored.path), stored])
    return stored
  }

  const form: Form = {
    app,
    record: detail.id,
    files,
    upload,
    set: (path, value) => setValues((current) => setPath(current, path, value) as Values),
  }
  const failed = save.error ?? remove.error

  return (
    <FormContext.Provider value={form}>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl text-ink">{app.title}</h1>
            <Link to={`/apps/${app.name}`} className="ml-auto text-sm text-ink underline-offset-4 hover:underline">
              All records
            </Link>
          </div>
          <Standing detail={detail} />
        </div>
        <Files record={detail.id} files={files} />
        <ErrorBanner error={failed && asApiError(failed)} className="whitespace-pre-line" />
        <RecordForm values={values} cursor={cursor} onCursor={setCursor} disabled={detail.removed} />
        {!detail.removed && (
          <div className="flex items-center gap-3">
            <Button variant="solid" size="lg" disabled={save.isPending} onClick={() => save.mutate()} data-testid="save">
              Save
            </Button>
            <Button variant="ghost" className="ml-auto text-err" onClick={() => setConfirming(true)} data-testid="remove">
              Remove
            </Button>
          </div>
        )}
        <History detail={detail} />
      </div>
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogTitle>Remove this record?</DialogTitle>
          <DialogDescription>
            It leaves the list, and the next Rebuild drops what it became. Its history stays in the audit log.
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <Button variant="ghost">Cancel</Button>
            </DialogClose>
            <Button
              variant="solid"
              className="bg-err hover:bg-err/90"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
              data-testid="remove-confirm"
            >
              Remove
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </FormContext.Provider>
  )
}

export function RecordView() {
  const { id = '' } = useParams()
  const record = useQuery({ queryKey: ['record', id], queryFn: () => getRecord(id) })
  const name = record.data?.app
  const app = useQuery({ queryKey: ['app', name], queryFn: () => getApp(name!), enabled: name !== undefined })
  const failed = record.error ?? app.error
  const state = failed ? 'error' : record.data && app.data ? 'ready' : 'loading'

  return (
    <div className="flex flex-col gap-5" data-testid="record-view" data-state={state}>
      <ErrorBanner error={failed && asApiError(failed)} />
      {record.data && app.data ? <Editor key={id} detail={record.data} app={app.data} /> : !failed && <Loading />}
    </div>
  )
}
