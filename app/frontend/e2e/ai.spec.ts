import type { Locator, Page, Route } from '@playwright/test'
import { expect, mockJson, NOW, openSelect, settle, snap, test, visit } from './fixtures'

const OFF = 'disabled · switched off in settings'
const BRIEFING = 'A fresh briefing for the snapshot.'
const FRESH = {
  role: 'ceo',
  briefing: BRIEFING,
  generated_at: NOW.toISOString(),
  model: 'claude-sonnet-5',
  prompt_version: '2026-08-02.1',
  input_sha: 'abc123def456',
  read: { metrics: 4, goals: 2, findings: 3 },
  inferred: true,
}
const STORED = {
  ...FRESH,
  read_manifest: { metrics: { mrr: 1, churn: 1, pipeline: 1, nps: 1 }, goals: { revenue: 1, retention: 1 }, findings: [1, 2, 3] },
}
const NO_FACTS = { total: 0, limit: 50, offset: 0, unverified_quotes: 0, by_value: {}, coverage: [], inferred: true, counts: '', facts: [] }

const patch = (page: Page, url: string, on: boolean) =>
  page.route(url, async (r) => {
    const j = await (await r.fetch()).json()
    await r.fulfill({ json: { ...j, enabled: on } })
  })

const layers = async (page: Page, on: boolean) => {
  await patch(page, '**/api/enrichment/vocabulary', on)
  await patch(page, '**/api/coaching', on)
}

const onGenerate = (page: Page, respond: (r: Route) => Promise<void>) =>
  page.route('**/api/coaching/ceo', (r) => (r.request().method() === 'POST' ? respond(r) : r.fallback()))

const headingRow = (page: Page) => page.getByRole('heading', { level: 1 }).locator('..')
const panel = (page: Page, name: string) => page.getByRole('tabpanel', { name })
const filters = (page: Page) => page.getByRole('combobox')
const column = (within: Locator, n: number) => within.locator(`tbody td:nth-child(${n})`)
const pick = (page: Page, option: string) => page.getByRole('option', { name: option, exact: true }).click()
const scrollBox = (of: Locator) => of.locator('xpath=ancestor::*[contains(@class,"overflow-y-auto")][1]')

const openEnrichment = async (page: Page) => {
  await layers(page, true)
  await visit(page, '/ai')
  return panel(page, 'Enrichment')
}

const openCoaching = async (page: Page) => {
  await page.getByRole('tab', { name: 'Coaching' }).click()
  await settle(page)
  return panel(page, 'Coaching')
}

const generate = async (page: Page) => {
  await page.getByRole('button', { name: 'Generate' }).click()
  await settle(page)
}

const above = async (a: Locator, b: Locator) => expect((await a.boundingBox())!.y).toBeLessThan((await b.boundingBox())!.y)

test('disabled', async ({ page }) => {
  await layers(page, false)
  await visit(page, '/ai')
  await expect(headingRow(page)).toContainText(OFF)
  const gate = panel(page, 'Enrichment').locator(':scope > div > div')
  await expect(gate).toHaveCSS('opacity', '0.5')
  await expect(gate).toHaveCSS('pointer-events', 'none')
  await snap(page, 'ai-disabled-enrichment')
  await openCoaching(page)
  await expect(headingRow(page)).toContainText(OFF)
  await snap(page, 'ai-disabled-coaching')
})

test('enabled', async ({ page }) => {
  const facts = await openEnrichment(page)
  await expect(headingRow(page)).not.toContainText(OFF)
  await expect(facts.getByRole('columnheader')).toHaveText(['Name (42)', 'Entity', 'Fact', 'Value', 'Verified', 'Quote'])
  await expect(filters(page)).toHaveText(['all entities (42)', 'all facts (42)', 'all values (42)', 'all quotes (42)'])
  await snap(page, 'ai-enrichment-default')
})

test('entity filter', async ({ page }) => {
  const facts = await openEnrichment(page)
  await openSelect(page, 'all entities')
  await pick(page, 'ticket (20)')
  await expect(facts.getByRole('columnheader').first()).toHaveText('Name (20)')
  await expect(filters(page)).toHaveText(['ticket (20)', 'all facts (20)', 'all values (20)', 'all quotes (20)'])
  await expect(column(facts, 2)).toHaveText(Array(20).fill('ticket'))
  await snap(page, 'ai-enrichment-ticket')
})

test('facts dropdown open on ticket', async ({ page }) => {
  await openEnrichment(page)
  await openSelect(page, 'all entities')
  await pick(page, 'ticket (20)')
  await expect(filters(page).nth(1)).toHaveText('all facts (20)')
  await openSelect(page, 'all facts')
  await expect(page.getByRole('option')).toHaveText(['all facts (20)', 'complaint (20)'])
  await snap(page, 'ai-enrichment-facts-open')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('listbox')).toHaveCount(0)
})

test('value filter', async ({ page }) => {
  const facts = await openEnrichment(page)
  await openSelect(page, 'all facts')
  await pick(page, 'complaint (20)')
  await expect(filters(page).nth(2)).toHaveText('all values (20)')
  await openSelect(page, 'all values')
  await pick(page, 'billing (6)')
  await expect(facts.getByRole('columnheader').first()).toHaveText('Name (6)')
  await expect(column(facts, 4)).toHaveText(Array(6).fill('billing'))
  await snap(page, 'ai-enrichment-value')
})

test('unverified only', async ({ page }) => {
  const facts = await openEnrichment(page)
  await openSelect(page, 'all quotes')
  await pick(page, 'unverified (5)')
  await expect(facts.getByRole('columnheader').first()).toHaveText('Name (5)')
  await expect(column(facts, 5)).toHaveText(Array(5).fill('unverified'))
  await snap(page, 'ai-enrichment-unverified')
})

test('empty facts', async ({ page }) => {
  await mockJson(page, '**/api/enrichment?*', NO_FACTS)
  await openEnrichment(page)
  await expect(page.getByText('no enriched facts')).toBeVisible()
  await expect(filters(page).first()).toHaveText('all entities (0)')
  await snap(page, 'ai-enrichment-empty')
})

test('scrolled', async ({ page }) => {
  const facts = await openEnrichment(page)
  const head = facts.getByRole('columnheader').first()
  const box = scrollBox(head)
  await box.evaluate((el) => (el.scrollTop = 400))
  await expect(box).toHaveJSProperty('scrollTop', 400)
  await expect(head).toBeInViewport()
  await expect(facts.locator('tbody tr').first()).not.toBeInViewport()
  await snap(page, 'ai-enrichment-scrolled')
})

test('coaching ceo', async ({ page }) => {
  await openEnrichment(page)
  const journal = await openCoaching(page)
  await expect(journal.getByRole('button', { name: 'CEO', exact: true, pressed: true })).toBeVisible()
  await expect(journal.getByRole('button', { name: 'HEAD_OF_SALES', pressed: false })).toBeVisible()
  await expect(journal.getByRole('columnheader')).toHaveText(['Generated (6)', 'Briefing', 'To', 'Read'])
  await expect(column(journal, 3)).toHaveText(Array(6).fill('maria.lopez@example.com'))
  await snap(page, 'ai-coaching-ceo')
})

test('coaching head of sales', async ({ page }) => {
  await openEnrichment(page)
  const journal = await openCoaching(page)
  await journal.getByRole('button', { name: 'HEAD_OF_SALES' }).click()
  await settle(page)
  await expect(journal.getByRole('button', { name: 'HEAD_OF_SALES', pressed: true })).toBeVisible()
  await expect(journal.getByRole('columnheader').first()).toHaveText('Generated (6)')
  await expect(column(journal, 3).first().locator('span > span')).toHaveText(['jane.smith@example.com', 'alex.chen@example.com'])
  await snap(page, 'ai-coaching-head-of-sales')
})

test('no briefing yet', async ({ page }) => {
  await mockJson(page, '**/api/coaching/ceo/history*', { role: 'ceo', briefings: [], inferred: true })
  await openEnrichment(page)
  await openCoaching(page)
  await expect(page.getByText('no briefing yet')).toBeVisible()
  await snap(page, 'ai-coaching-empty')
})

test('just generated', async ({ page }) => {
  let generated = false
  await page.route('**/api/coaching/ceo/history*', async (r) => {
    const j = await (await r.fetch()).json()
    await r.fulfill({ json: generated ? { ...j, briefings: [STORED, ...j.briefings] } : j })
  })
  await onGenerate(page, (r) => {
    generated = true
    return r.fulfill({ json: FRESH })
  })
  await openEnrichment(page)
  const journal = await openCoaching(page)
  await generate(page)
  const first = journal.locator('tbody tr').first()
  await expect(first).toContainText('just generated')
  await expect(first).toContainText(BRIEFING)
  await expect(journal.getByRole('columnheader').first()).toHaveText('Generated (7)')
  await snap(page, 'ai-coaching-generated')
})

test('generate error', async ({ page }) => {
  await onGenerate(page, (r) => r.fulfill({ status: 409, json: { detail: 'COACHING_ENABLED is off' } }))
  await openEnrichment(page)
  const journal = await openCoaching(page)
  await generate(page)
  const off = page.getByRole('status').filter({ hasText: 'COACHING_ENABLED is off' })
  await expect(off).toBeVisible()
  await expect(scrollBox(off)).toHaveCount(0)
  await above(off, journal.locator('table'))
  await snap(page, 'ai-coaching-generate-error')

  await onGenerate(page, (r) => r.fulfill({ status: 500, json: { detail: 'model call failed' } }))
  await generate(page)
  const failed = page.getByRole('alert')
  await expect(failed).toHaveText('500 model call failed')
  await expect(off).toHaveCount(0)
  await above(failed, journal.locator('table'))
  await snap(page, 'ai-coaching-generate-failed')
})
