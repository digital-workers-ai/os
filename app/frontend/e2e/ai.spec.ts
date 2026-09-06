import type { Locator, Page, Route } from '@playwright/test'
import { expect, mockJson, NOW, openFilter, pickOption, settle, snap, test, visit } from './fixtures'

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
const FILTERS = ['facts-entity-filter', 'facts-fact-filter', 'facts-value-filter', 'facts-quote-filter']

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

const badge = (page: Page) => page.getByTestId('page-heading-row').getByTestId('page-badge')
const heads = (table: Locator) => table.locator('th')
const column = (rows: Locator, n: number) => rows.locator(`td:nth-child(${n})`)
const options = (page: Page, filter: string) => page.getByTestId(`${filter}-option`)

const expectFilters = async (page: Page, texts: string[]) => {
  for (const [i, id] of FILTERS.entries()) await expect(page.getByTestId(id)).toHaveText(texts[i])
}

const expectGated = async (gate: Locator) => {
  await expect(gate).toHaveCSS('cursor', 'not-allowed')
  const shade = gate.locator(':scope > div')
  await expect(shade).toHaveCSS('opacity', '0.5')
  await expect(shade).toHaveCSS('pointer-events', 'none')
}

const openEnrichment = async (page: Page) => {
  await layers(page, true)
  await visit(page, '/ai')
  return page.getByTestId('facts')
}

const openCoaching = async (page: Page) => {
  await page.getByTestId('tab-coaching').click()
  await settle(page)
  return page.getByTestId('coaching')
}

const generate = async (page: Page) => {
  await page.getByTestId('coaching-generate').click()
  await settle(page)
}

const expectInHeader = async (page: Page, testId: string) => {
  await expect(page.getByTestId('coaching-description').getByTestId(testId)).toHaveCount(1)
  await expect(page.getByTestId('coaching-body').getByTestId(testId)).toHaveCount(0)
}

test('disabled', async ({ page }) => {
  await layers(page, false)
  await visit(page, '/ai')
  await expect(badge(page)).toHaveText(OFF)
  await expectGated(page.getByTestId('ai-gate-enrichment'))
  await snap(page, 'ai-disabled-enrichment')
  await openCoaching(page)
  await expect(badge(page)).toHaveText(OFF)
  await expectGated(page.getByTestId('ai-gate-coaching'))
  await snap(page, 'ai-disabled-coaching')
})

test('enabled', async ({ page }) => {
  const facts = await openEnrichment(page)
  await expect(badge(page)).toHaveCount(0)
  await expect(heads(facts.getByTestId('facts-table'))).toHaveText(['Name (42)', 'Entity', 'Fact', 'Value', 'Verified', 'Quote'])
  await expectFilters(page, ['all entities (42)', 'all facts (42)', 'all values (42)', 'all quotes (42)'])
  await snap(page, 'ai-enrichment-default')
})

test('entity filter', async ({ page }) => {
  const facts = await openEnrichment(page)
  await pickOption(page, 'facts-entity-filter', 'ticket')
  await expect(heads(facts.getByTestId('facts-table')).first()).toHaveText('Name (20)')
  await expectFilters(page, ['ticket (20)', 'all facts (20)', 'all values (20)', 'all quotes (20)'])
  await expect(column(facts.getByTestId('facts-row'), 2)).toHaveText(Array(20).fill('ticket'))
  await snap(page, 'ai-enrichment-ticket')
})

test('facts dropdown open on ticket', async ({ page }) => {
  await openEnrichment(page)
  await pickOption(page, 'facts-entity-filter', 'ticket')
  await expect(page.getByTestId('facts-fact-filter')).toHaveText('all facts (20)')
  await openFilter(page, 'facts-fact-filter')
  await expect(options(page, 'facts-fact-filter')).toHaveText(['all facts (20)', 'complaint (20)'])
  await snap(page, 'ai-enrichment-facts-open')
  await page.keyboard.press('Escape')
  await expect(options(page, 'facts-fact-filter')).toHaveCount(0)
})

test('value filter', async ({ page }) => {
  const facts = await openEnrichment(page)
  await pickOption(page, 'facts-fact-filter', 'complaint')
  await expect(page.getByTestId('facts-value-filter')).toHaveText('all values (20)')
  await pickOption(page, 'facts-value-filter', 'billing')
  await expect(heads(facts.getByTestId('facts-table')).first()).toHaveText('Name (6)')
  await expect(column(facts.getByTestId('facts-row'), 4)).toHaveText(Array(6).fill('billing'))
  await snap(page, 'ai-enrichment-value')
})

test('unverified only', async ({ page }) => {
  const facts = await openEnrichment(page)
  await pickOption(page, 'facts-quote-filter', 'unverified')
  await expect(heads(facts.getByTestId('facts-table')).first()).toHaveText('Name (5)')
  await expect(facts.getByTestId('facts-verified')).toHaveText(Array(5).fill('unverified'))
  await snap(page, 'ai-enrichment-unverified')
})

test('empty facts', async ({ page }) => {
  await mockJson(page, '**/api/enrichment?*', NO_FACTS)
  const facts = await openEnrichment(page)
  await expect(facts.getByTestId('empty')).toHaveText('no enriched facts')
  await expect(page.getByTestId('facts-entity-filter')).toHaveText('all entities (0)')
  await snap(page, 'ai-enrichment-empty')
})

test('scrolled', async ({ page }) => {
  const facts = await openEnrichment(page)
  const head = heads(facts.getByTestId('facts-table')).first()
  const body = facts.getByTestId('facts-body')
  await expect(head).toBeVisible()
  await body.evaluate((el) => (el.scrollTop = 400))
  await expect(body).toHaveJSProperty('scrollTop', 400)
  await expect(head).toBeInViewport()
  await expect(facts.getByTestId('facts-row').first()).not.toBeInViewport()
  await snap(page, 'ai-enrichment-scrolled')
})

test('coaching ceo', async ({ page }) => {
  await openEnrichment(page)
  const journal = await openCoaching(page)
  const ceo = journal.getByTestId('coaching-role-ceo')
  const sales = journal.getByTestId('coaching-role-head_of_sales')
  await expect(ceo).toHaveText('CEO')
  await expect(ceo).toHaveAttribute('aria-pressed', 'true')
  await expect(sales).toHaveText('HEAD_OF_SALES')
  await expect(sales).toHaveAttribute('aria-pressed', 'false')
  await expect(heads(journal.getByTestId('coaching-journal'))).toHaveText(['Generated (6)', 'Briefing', 'To', 'Read'])
  await expect(journal.getByTestId('coaching-to')).toHaveText(Array(6).fill('maria.lopez@example.com'))
  await snap(page, 'ai-coaching-ceo')
})

test('coaching head of sales', async ({ page }) => {
  await openEnrichment(page)
  const journal = await openCoaching(page)
  const sales = journal.getByTestId('coaching-role-head_of_sales')
  await sales.click()
  await settle(page)
  await expect(sales).toHaveAttribute('aria-pressed', 'true')
  await expect(heads(journal.getByTestId('coaching-journal')).first()).toHaveText('Generated (6)')
  await expect(journal.getByTestId('coaching-row').first().getByTestId('coaching-to')).toHaveText(['jane.smith@example.com', 'alex.chen@example.com'])
  await snap(page, 'ai-coaching-head-of-sales')
})

test('no briefing yet', async ({ page }) => {
  await mockJson(page, '**/api/coaching/ceo/history*', { role: 'ceo', briefings: [], inferred: true })
  await openEnrichment(page)
  const journal = await openCoaching(page)
  await expect(journal.getByTestId('empty')).toHaveText('no briefing yet')
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
  const first = journal.getByTestId('coaching-row').first()
  await expect(first.getByTestId('coaching-fresh')).toHaveText('just generated')
  await expect(first).toContainText(BRIEFING)
  await expect(heads(journal.getByTestId('coaching-journal')).first()).toHaveText('Generated (7)')
  await snap(page, 'ai-coaching-generated')
})

test('generate error', async ({ page }) => {
  await onGenerate(page, (r) => r.fulfill({ status: 409, json: { detail: 'COACHING_ENABLED is off' } }))
  await openEnrichment(page)
  const journal = await openCoaching(page)
  await generate(page)
  const off = journal.getByTestId('banner')
  await expect(off).toHaveText('COACHING_ENABLED is off')
  await expectInHeader(page, 'banner')
  await snap(page, 'ai-coaching-generate-error')

  await onGenerate(page, (r) => r.fulfill({ status: 500, json: { detail: 'model call failed' } }))
  await generate(page)
  const failed = journal.getByTestId('error-banner')
  await expect(failed).toHaveText('500 model call failed')
  await expect(off).toHaveCount(0)
  await expectInHeader(page, 'error-banner')
  await snap(page, 'ai-coaching-generate-failed')
})
