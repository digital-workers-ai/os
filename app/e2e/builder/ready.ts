import type { Page } from '@playwright/test'
import { expect, NOW, settle } from '../fixtures'

export interface Suggestion {
  app: string | null
  title: string
  reason: string
}

export interface Turn {
  role: 'person' | 'builder'
  text: string
  questions: string[]
  suggestions: Suggestion[]
  draft: string | null
  problems: string[]
}

export interface Issue {
  number: number
  url: string
}

export interface ThreadRow {
  id: string
  app: string | null
  title: string | null
  created_at: string
  issue: Issue | null
}

export interface Thread extends ThreadRow {
  turns: Turn[]
}

export const THREAD_ID = '3f6c1d2e-9a4b-4c8d-b7e5-1a2b3c4d5e6f'

export const ISSUE: Issue = { number: 41, url: 'https://github.com/digital-workers-ai/os/issues/41' }

export const person = (text: string): Turn => ({ role: 'person', text, questions: [], suggestions: [], draft: null, problems: [] })

export const builder = (text: string, answer: Partial<Turn> = {}): Turn => ({ ...person(text), role: 'builder', ...answer })

export async function ready(page: Page) {
  await expect(page.getByTestId('page-main')).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('[data-state="loading"]')).toHaveCount(0, { timeout: 30_000 })
  await expect(page.getByTestId('loading')).toHaveCount(0, { timeout: 30_000 })
  await page.evaluate(() => window.scrollTo(0, 0))
  await settle(page)
}

function titleOf(turns: Turn[]): string | null {
  const latest = [...turns].reverse().find((turn) => turn.draft !== null)
  return latest ? (/^title: (.+)$/m.exec(latest.draft!)?.[1] ?? null) : null
}

export async function mockBuilder(
  page: Page,
  { turns = [], replies = [], reading = null }: { turns?: Turn[]; replies?: Turn[]; reading?: unknown } = {},
) {
  const thread: Thread = { id: THREAD_ID, app: null, title: null, created_at: NOW.toISOString(), issue: null, turns: [...turns] }
  const row = (): ThreadRow => {
    const { turns: said, ...rest } = thread
    return { ...rest, title: titleOf(said) }
  }
  let next = 0
  await page.route(/\/api\/builder\/threads/, (route) => {
    const request = route.request()
    const [id, action] = new URL(request.url()).pathname.split('/').slice(4)
    if (!id && request.method() === 'GET') return route.fulfill({ json: [row()] })
    if (!id) {
      thread.app = (request.postDataJSON() as { app?: string } | null)?.app ?? null
      return route.fulfill({ status: 201, json: { ...row(), turns: [] } })
    }
    if (!action) return route.fulfill({ json: { ...row(), turns: thread.turns } })
    if (action === 'turns') {
      const said = person((request.postDataJSON() as { text: string }).text)
      const reply = replies[next++]
      thread.turns.push(said, reply)
      return route.fulfill({ json: { turn: said, reply } })
    }
    if (action === 'try') return route.fulfill({ json: reading })
    thread.issue = ISSUE
    return route.fulfill({ json: ISSUE })
  })
}

export const sent = (page: Page, path: string) =>
  page.waitForRequest((r) => r.method() === 'POST' && new URL(r.url()).pathname === `/api/builder/${path}`)

export const turned = (page: Page) => sent(page, `threads/${THREAD_ID}/turns`)

export async function say(page: Page, text: string): Promise<unknown> {
  const request = turned(page)
  await page.getByTestId('composer-input').fill(text)
  await page.getByTestId('composer-send').click()
  return (await request).postDataJSON()
}

export async function opened(page: Page) {
  await expect(page).toHaveURL(new RegExp(`/threads/${THREAD_ID}$`))
  await ready(page)
}
