import { useState, type FormEvent } from 'react'
import {
  asApiError,
  del,
  get,
  post,
  type ApiError,
  type ApiKeyCreated,
  type ApiKeyRow,
  type McpCallerRow,
  type McpClientRow,
} from '@/api'
import { useMe } from '@/components/AuthGate'
import { SectionCard } from '@/components/SectionCard'
import { ErrorBanner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Empty } from '@/components/ui/empty'
import { Input } from '@/components/ui/input'
import { Loading } from '@/components/ui/loading'
import { Mono } from '@/components/ui/mono'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { num, relTime, when } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLoad } from './inference/shared'

const NUM = 'text-right tabular-nums'
const KEY = 'font-medium text-ink'
const TOP = 'align-top'
const NARROW = 'w-px whitespace-nowrap'
const ACTION = 'pr-0 text-right'
const LEAD = 'text-sm text-muted'

const OPEN = 'Access is open. Set AUTH_ENABLED to require Google sign-in; API keys and connected clients appear then.'

function Revoke({ onConfirm, testId }: { onConfirm: () => Promise<void>; testId: string }) {
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const click = async () => {
    if (!armed) {
      setArmed(true)
      return
    }
    setBusy(true)
    try {
      await onConfirm()
    } finally {
      setBusy(false)
      setArmed(false)
    }
  }
  return (
    <Button size="sm" variant="outline" disabled={busy} onClick={click} data-testid={testId}>
      {busy ? 'revoking…' : armed ? 'Confirm' : 'Revoke'}
    </Button>
  )
}

function Me() {
  const me = useMe()
  const [error, setError] = useState<ApiError | null>(null)
  const signOut = async () => {
    setError(null)
    try {
      await post<void>('/api/auth/logout')
      window.location.reload()
    } catch (e) {
      setError(asApiError(e))
    }
  }
  return (
    <SectionCard testId="access-me">
      <ErrorBanner error={error} className="mb-3" />
      {me.auth === 'open' ? (
        <p className={LEAD}>{OPEN}</p>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <p className={LEAD}>
            Signed in as <span className={KEY}>{me.email}</span>
          </p>
          <Button size="sm" variant="outline" onClick={signOut} data-testid="access-signout">
            Sign out
          </Button>
        </div>
      )}
    </SectionCard>
  )
}

function Keys() {
  const keys = useLoad(() => get<ApiKeyRow[]>('/api/auth/keys'), [])
  const [creating, setCreating] = useState(false)
  const [label, setLabel] = useState('')
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState<ApiKeyCreated | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const list = keys.data ?? []

  const create = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setCreated(await post<ApiKeyCreated>('/api/auth/keys', { label: label.trim() }))
      setCreating(false)
      setLabel('')
      keys.reload()
    } catch (err) {
      setError(asApiError(err))
    } finally {
      setBusy(false)
    }
  }

  const revoke = async (seq: number) => {
    setError(null)
    try {
      await del(`/api/auth/keys/${seq}`)
      keys.reload()
    } catch (e) {
      setError(asApiError(e))
    }
  }

  const copy = () => {
    if (!created || !navigator.clipboard) return
    navigator.clipboard
      .writeText(created.key)
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      })
      .catch(() => {})
  }

  return (
    <SectionCard
      testId="access-keys"
      title="API keys"
      headerRight={
        <Button size="sm" disabled={creating} onClick={() => setCreating(true)} data-testid="access-keys-new">
          New key
        </Button>
      }
    >
      <ErrorBanner error={keys.error ?? error} className="mb-3" />
      {creating && (
        <form className="mb-3 flex gap-2" onSubmit={create}>
          <Input
            autoFocus
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label"
            className="h-8 max-w-xs"
            data-testid="access-keys-label"
          />
          <Button type="submit" size="sm" disabled={busy || !label.trim()} data-testid="access-keys-create">
            {busy ? 'creating…' : 'Create'}
          </Button>
        </form>
      )}
      {created && (
        <div className="mb-3 rounded-lg border border-line bg-wash p-3" data-testid="access-keys-created">
          <p className={cn(LEAD, 'mb-2')}>Copy it now; it is shown once.</p>
          <div className="flex items-center justify-between gap-3">
            <Mono className="text-ink">{created.key}</Mono>
            <Button size="sm" variant="outline" onClick={copy} data-testid="access-keys-copy">
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
        </div>
      )}
      {keys.loading && <Loading />}
      {keys.data && list.length === 0 && <Empty>no keys yet</Empty>}
      {list.length > 0 && (
        <Table data-testid="access-keys-table">
          <TableHeader>
            <TableRow>
              <TableHead hint="The name given to the key when it was created">Label</TableHead>
              <TableHead hint="The start of the key, enough to tell keys apart">Prefix</TableHead>
              <TableHead hint="Who created the key">Created by</TableHead>
              <TableHead hint="When the key was created">Created</TableHead>
              <TableHead hint="When the key last authenticated a call">Last used</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.map((k) => (
              <TableRow key={k.seq}>
                <TableCell className={cn(KEY, TOP)}>{k.label}</TableCell>
                <TableCell className={cn(NARROW, TOP)}>
                  <Mono>{k.prefix}…</Mono>
                </TableCell>
                <TableCell className={TOP}>{k.created_by}</TableCell>
                <TableCell className={TOP} title={k.created_at}>
                  {when(k.created_at)}
                </TableCell>
                <TableCell className={TOP} title={k.last_used_at ?? undefined}>
                  {relTime(k.last_used_at)}
                </TableCell>
                <TableCell className={cn(ACTION, TOP)}>
                  <Revoke onConfirm={() => revoke(k.seq)} testId="access-keys-revoke" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </SectionCard>
  )
}

function Clients() {
  const clients = useLoad(() => get<McpClientRow[]>('/api/auth/clients'), [])
  const [error, setError] = useState<ApiError | null>(null)
  const list = clients.data ?? []

  const revoke = async (seq: number) => {
    setError(null)
    try {
      await del(`/api/auth/clients/${seq}`)
      clients.reload()
    } catch (e) {
      setError(asApiError(e))
    }
  }

  return (
    <SectionCard testId="access-clients" title="Connected clients">
      <ErrorBanner error={clients.error ?? error} className="mb-3" />
      {clients.loading && <Loading />}
      {clients.data && list.length === 0 && <Empty>no clients have connected</Empty>}
      {list.length > 0 && (
        <Table data-testid="access-clients-table">
          <TableHeader>
            <TableRow>
              <TableHead hint="The MCP client that connected and where it receives tokens">Client</TableHead>
              <TableHead hint="Who authorized the client">Person</TableHead>
              <TableHead hint="When the person authorized the client">Authorized</TableHead>
              <TableHead hint="When the client last called">Last seen</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.map((c) => (
              <TableRow key={c.seq}>
                <TableCell className={TOP}>
                  <span className={cn(KEY, 'block')}>{c.client_name}</span>
                  <Mono>{c.redirect_uri}</Mono>
                </TableCell>
                <TableCell className={TOP}>{c.email}</TableCell>
                <TableCell className={TOP} title={c.created_at}>
                  {when(c.created_at)}
                </TableCell>
                <TableCell className={TOP} title={c.last_seen_at ?? undefined}>
                  {relTime(c.last_seen_at)}
                </TableCell>
                <TableCell className={cn(ACTION, TOP)}>
                  <Revoke onConfirm={() => revoke(c.seq)} testId="access-clients-revoke" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </SectionCard>
  )
}

function Callers() {
  const callers = useLoad(() => get<McpCallerRow[]>('/api/mcp/calls'), [])
  const list = callers.data ?? []
  return (
    <SectionCard testId="access-callers" title="Callers">
      <ErrorBanner error={callers.error} className="mb-3" />
      {callers.loading && <Loading />}
      {callers.data && list.length === 0 && <Empty>no calls yet</Empty>}
      {list.length > 0 && (
        <Table data-testid="access-callers-table">
          <TableHeader>
            <TableRow>
              <TableHead hint="Who made the calls, or open when nobody had to sign in">Person</TableHead>
              <TableHead hint="The tool that was called">Tool</TableHead>
              <TableHead className={NUM} hint="How many times it was called">
                Calls
              </TableHead>
              <TableHead className={NUM} hint="How many of those calls failed">
                Failed
              </TableHead>
              <TableHead hint="When the tool was last called">Last call</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.map((r) => (
              <TableRow key={`${r.subject ?? ''}|${r.name}`}>
                <TableCell className={TOP}>
                  {r.subject === null ? <span className="text-muted">open</span> : <span className={KEY}>{r.subject}</span>}
                </TableCell>
                <TableCell className={cn(NARROW, TOP)}>
                  <Mono>{r.name}</Mono>
                </TableCell>
                <TableCell className={cn(NUM, TOP)}>{num(r.calls)}</TableCell>
                <TableCell className={cn(NUM, TOP)}>{num(r.failed)}</TableCell>
                <TableCell className={TOP} title={r.last_at}>
                  {relTime(r.last_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </SectionCard>
  )
}

export function Access() {
  const me = useMe()
  return (
    <div className="space-y-6">
      <Me />
      {me.auth === 'google' && (
        <>
          <Keys />
          <Clients />
        </>
      )}
      <Callers />
    </div>
  )
}
