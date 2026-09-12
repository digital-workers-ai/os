import { test as base, expect, type Locator, type Page } from '@playwright/test'

const pinned = process.env.CLOCK_PINNED_AT
if (!pinned || Number.isNaN(Date.parse(pinned))) {
  throw new Error('CLOCK_PINNED_AT is not set; docker-compose.snap.yml pins it for the snap stack')
}
export const NOW = new Date(pinned)

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.clock.setFixedTime(NOW)
    await use(page)
  },
})

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export function header(scope: Locator | Page, label: string | RegExp) {
  return scope.locator('th').filter({ hasText: typeof label === 'string' ? new RegExp(`^${escape(label)}$`) : label })
}

export async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForLoadState('networkidle')
  await expect(page.getByTestId('loading')).toHaveCount(0)
}

export async function visit(page: Page, path: string) {
  await page.goto(path)
  await settle(page)
}

export async function snap(
  page: Page,
  name: string,
  options?: Parameters<ReturnType<typeof expect<Page>>['toHaveScreenshot']>[1],
) {
  await expect(page).toHaveScreenshot(`${name}.png`, options)
}

export async function openFilter(page: Page, testId: string) {
  await page.getByTestId(testId).click()
  await page.locator('[role=listbox]').waitFor()
}

export async function pickOption(page: Page, testId: string, value: string) {
  await openFilter(page, testId)
  await page.locator(`[data-testid="${testId}-option"][data-value="${value}"]`).click()
}

export async function mockJson(page: Page, url: string, body: unknown, status = 200) {
  await page.route(url, r => r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) }))
}

export interface Candidate {
  seq: number
  entity_type: string
  left: { anchor: string; canonical_id: string; label: string }
  right: { anchor: string; canonical_id: string; label: string }
  score: number
  status: 'pending' | 'confirmed' | 'rejected'
  evidence_holds: boolean
  decided_at: string | null
  evidence: { attr: string; left_value: string; right_value: string }[]
}

const side = (anchor: string, label: string) => ({ anchor, canonical_id: `can_${anchor.split('|').pop()}`, label })
const differ = (attr: string, left_value: string, right_value: string) => ({ attr, left_value, right_value })
const agree = (attr: string, value: string) => differ(attr, value, value)

export const CANDIDATES: Candidate[] = [
  {
    seq: 1,
    entity_type: 'person',
    left: side('hubspot|contact|c_101', 'Carlos Ch'),
    right: side('stripe|customer|cus_101', 'C Chinchilla'),
    score: 0.82,
    status: 'pending',
    evidence_holds: true,
    decided_at: null,
    evidence: [differ('name', 'Carlos Ch', 'C Chinchilla'), agree('phone', '+1 415 555 0101')],
  },
  {
    seq: 2,
    entity_type: 'person',
    left: side('hubspot|contact|c_202', 'Maria Lopez'),
    right: side('intercom|user|u_202', 'M. Lopez'),
    score: 0.86,
    status: 'confirmed',
    evidence_holds: false,
    decided_at: '2026-09-03T10:00:00Z',
    evidence: [differ('name', 'Maria Lopez', 'M. Lopez'), agree('email_domain', 'acme.io')],
  },
  {
    seq: 3,
    entity_type: 'person',
    left: side('hubspot|contact|c_303', 'Bob Chen'),
    right: side('stripe|customer|cus_303', 'Robert Chen'),
    score: 0.9,
    status: 'rejected',
    evidence_holds: true,
    decided_at: '2026-09-02T16:30:00Z',
    evidence: [differ('name', 'Bob Chen', 'Robert Chen'), agree('email_domain', 'chen.dev')],
  },
]

export async function mockCandidates(page: Page, candidates: Candidate[] = CANDIDATES) {
  await page.route('**/api/resolution/candidates*', (r) => {
    const status = new URL(r.request().url()).searchParams.get('status')
    const counts = { pending: 0, confirmed: 0, rejected: 0 }
    for (const c of candidates) counts[c.status]++
    const list = status === 'all' ? candidates : candidates.filter((c) => c.status === status)
    return r.fulfill({ json: { candidates: list, counts } })
  })
}

export { expect }
