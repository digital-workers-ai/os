import { Fragment, useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Search as SearchIcon } from 'lucide-react'
import { asApiError, get, type ApiError, type SearchHit, type SearchResponse } from '@/api'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Empty } from '@/components/ui/empty'
import { Loading } from '@/components/ui/loading'
import { hrefFor } from '@/lib/hrefFor'
import { anchorText, num } from '@/lib/format'
import { cn } from '@/lib/utils'
import { PATH } from '@/paths'
import { ROUTES, SEARCH_ROUTE } from '@/routes'
import { ANCHOR_ATTR, DEFAULT_LIMIT, EVIDENCE_SEP, LABEL_SEP, MIN_QUERY_CHARS, PARAM, RECENT_KEY, SEARCH_API } from '@/search/vocab'

const MAX_RECENT = 5
const DEBOUNCE_MS = 150
const ROW = 'block w-full px-3 py-2 text-left text-sm text-dbb-charcoal hover:bg-black/[0.04]'
const HEADING = 'px-3 pb-1 pt-2 text-[11px] uppercase tracking-wide text-dbb-muted'

const GOTO = ROUTES.filter((route) => route !== SEARCH_ROUTE).flatMap((route) => [
  { label: route.label, to: route.to },
  ...(route.tabs ?? []).map((tab) => ({ label: `${route.label}${LABEL_SEP}${tab.label}`, to: `${route.to}/${tab.value}` })),
])

function readRecent(): string[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter((s): s is string => typeof s === 'string').slice(0, MAX_RECENT) : []
  } catch {
    return []
  }
}

function remember(q: string) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify([q, ...readRecent().filter((s) => s !== q)].slice(0, MAX_RECENT)))
  } catch {
    return
  }
}

const evidenceText = (evidence: string) => (evidence.startsWith(`${ANCHOR_ATTR}${EVIDENCE_SEP}`) ? anchorText(evidence) : evidence)

const groupByKind = (hits: SearchHit[]) =>
  [...new Set(hits.map((hit) => hit.kind))].flatMap((kind) => hits.filter((hit) => hit.kind === kind))

function Palette({ close }: { close: () => void }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [got, setGot] = useState<{ q: string; res: SearchResponse } | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [active, setActive] = useState(-1)
  const [recent] = useState(readRecent)
  const q = query.trim()

  useEffect(() => {
    if (q.length < MIN_QUERY_CHARS) {
      setGot(null)
      setError(null)
      return
    }
    let live = true
    const timer = setTimeout(() => {
      get<SearchResponse>(`${SEARCH_API}?${PARAM.q}=${encodeURIComponent(q)}&${PARAM.limit}=${DEFAULT_LIMIT}`)
        .then((res) => {
          if (!live) return
          setGot({ q, res })
          setError(null)
          setActive(-1)
        })
        .catch((e) => {
          if (!live) return
          setGot(null)
          setError(asApiError(e))
        })
    }, DEBOUNCE_MS)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [q])

  useEffect(() => {
    document.getElementById(`search-option-${active}`)?.scrollIntoView({ block: 'nearest' })
  }, [active])

  const res = got?.res ?? null
  const rows = useMemo(() => groupByKind((res?.results ?? []).slice(0, DEFAULT_LIMIT)), [res])
  const fresh = got?.q === q ? got.res : null
  const allHref = fresh?.kind
    ? `${PATH.search}?${PARAM.q}=${encodeURIComponent(fresh.q)}&${PARAM.kind}=${encodeURIComponent(fresh.kind)}`
    : `${PATH.search}?${PARAM.q}=${encodeURIComponent(q)}`

  const go = (href: string) => {
    if (q) remember(q)
    close()
    navigate(href)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => Math.min(i + 1, rows.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(i - 1, -1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const hit = rows[active]
      go(hit ? hrefFor(hit.kind, hit.id) : allHref)
    }
  }

  const body =
    q.length < MIN_QUERY_CHARS ? (
      <>
        {recent.length > 0 && (
          <div>
            <div className={HEADING}>Recent</div>
            {recent.map((item) => (
              <button key={item} type="button" data-testid="search-recent" className={ROW} onClick={() => setQuery(item)}>
                {item}
              </button>
            ))}
          </div>
        )}
        <div>
          <div className={HEADING}>Go to</div>
          {GOTO.map((page) => (
            <Link key={page.to} to={page.to} data-testid="search-goto" className={ROW} onClick={close}>
              {page.label}
            </Link>
          ))}
        </div>
      </>
    ) : error ? (
      <Empty testId="search-status">search unavailable: {error.detail}</Empty>
    ) : !res ? (
      <Loading />
    ) : rows.length === 0 ? (
      <Empty testId="search-status">no matches</Empty>
    ) : (
      <div role="listbox" id="search-listbox">
        {rows.map((hit, i) => (
          <Fragment key={`${hit.kind}/${hit.id}`}>
            {(i === 0 || rows[i - 1].kind !== hit.kind) && (
              <div data-testid="search-group" data-kind={hit.kind} className={HEADING}>
                {hit.kind.replaceAll('_', ' ')}
              </div>
            )}
            <div
              id={`search-option-${i}`}
              role="option"
              aria-selected={i === active}
              data-testid="search-result"
              data-kind={hit.kind}
              data-id={hit.id}
              className={cn(ROW, 'flex cursor-pointer items-baseline gap-3', i === active && 'bg-black/[0.04]')}
              onClick={() => go(hrefFor(hit.kind, hit.id))}
            >
              <span className="max-w-[60%] shrink-0 truncate">{anchorText(hit.label)}</span>
              <span className="min-w-0 flex-1 truncate text-dbb-muted">{evidenceText(hit.evidence)}</span>
            </div>
          </Fragment>
        ))}
      </div>
    )

  return (
    <>
      <div className="flex items-center gap-2 border-b border-dbb-warm px-3">
        <SearchIcon size={16} className="shrink-0 text-dbb-muted" />
        <input
          data-testid="search-input"
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Search everything…"
          aria-controls="search-listbox"
          aria-activedescendant={active >= 0 ? `search-option-${active}` : undefined}
          className="h-11 w-full bg-transparent text-sm text-dbb-charcoal placeholder:text-dbb-muted focus:outline-none"
        />
        <kbd className="rounded border border-dbb-warm px-1.5 py-0.5 text-[10px] text-dbb-muted">Esc</kbd>
      </div>
      <div className="max-h-[60vh] overflow-y-auto py-1">{body}</div>
      <div className="flex items-center justify-between border-t border-dbb-warm px-3 py-2 text-[11px] text-dbb-muted">
        <span>↑↓ move · ↵ open</span>
        {res && res.total > 0 && (
          <Link
            to={allHref}
            data-testid="search-all"
            className="hover:text-dbb-charcoal"
            onClick={() => {
              remember(q)
              close()
            }}
          >
            View all {num(res.total)} →
          </Link>
        )}
      </div>
    </>
  )
}

export function CommandPalette({ enabled }: { enabled: boolean }) {
  const [open, setOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    setOpen(false)
  }, [location])

  useEffect(() => {
    if (!enabled) return
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enabled])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent data-testid="search-palette" aria-describedby={undefined}>
        <DialogTitle>Search</DialogTitle>
        <Palette close={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  )
}
