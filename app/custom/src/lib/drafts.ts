import { useCallback, useRef, useState } from 'react'
import type { Cursor, RecordFile, Values } from '@/api'

export interface Draft {
  record: string | null
  fields: Values
  files: RecordFile[]
  scan: string | null
  cursor: Cursor | null
}

const key = (app: string) => `dw-apps-draft:${app}`

function readDraft(app: string): Draft | null {
  try {
    const text = localStorage.getItem(key(app))
    return text ? (JSON.parse(text) as Draft) : null
  } catch {
    return null
  }
}

function writeDraft(app: string, draft: Draft) {
  localStorage.setItem(key(app), JSON.stringify(draft))
}

export function dropDraft(app: string) {
  localStorage.removeItem(key(app))
}

export function useDraft(app: string, blank: () => Draft) {
  const [draft, setDraft] = useState<Draft>(() => readDraft(app) ?? blank())
  const latest = useRef(draft)
  const change = useCallback(
    (next: (draft: Draft) => Draft) => {
      latest.current = next(latest.current)
      writeDraft(app, latest.current)
      setDraft(latest.current)
    },
    [app],
  )
  return { draft, latest, change }
}
