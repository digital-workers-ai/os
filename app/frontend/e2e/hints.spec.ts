import type { Page, Route } from '@playwright/test'
import { expect, mockCandidates, mockJson, NOW, settle, snap, test, visit } from './fixtures'

const DEFINITIONS: Record<string, string[]> = {
  ontology: ['definitions-ontology-table', 'definitions-relationships-table'],
  mappings: ['definitions-mappings-table'],
  transforms: ['definitions-transforms-table', 'definitions-transforms-functions-table'],
  metrics: ['definitions-metrics-table'],
  derived: ['definitions-derived-table'],
  rules: ['definitions-rules-table'],
  goals: ['definitions-goals-table'],
  enrichment: ['definitions-enrichment-table'],
}

const MCP = {
  path: '/mcp',
  tools: [{ name: 'get_metrics', description: 'Metric series with current value and trend' }],
  resources: [{ uri: 'definitions://ontology', name: 'ontology', description: 'Committed ontology definitions' }],
  prompts: [{ name: 'briefing_ceo', description: 'CEO briefing from the current estate' }],
}

const series = (r: Route) => ({
  metric: decodeURIComponent(r.request().url().split('/').pop()!),
  runs: [{ inferred: false, vocabulary_sha: null, produced_by: null, points: [{ value: 120, entities: 5, recorded_at: NOW.toISOString() }] }],
  comparable: true,
  breaks: 0,
  inferred: false,
})

const enable = (page: Page, url: string) =>
  page.route(url, async (r) => {
    const j = await (await r.fetch()).json()
    await r.fulfill({ json: { ...j, enabled: true } })
  })

const collect = (page: Page) => page.getByTestId('hint').evaluateAll((els) => els.map((el) => el.getAttribute('aria-label') ?? ''))

const headers = (page: Page) => page.locator('th').filter({ hasText: /\S/ })

const audit = async (page: Page, state: string) => {
  const ths = headers(page)
  const n = await ths.count()
  await test.step(`${state}: ${n} headers`, async () => {
    expect(n).toBeGreaterThan(0)
    for (const th of await ths.all()) await expect(th.getByTestId('hint')).toHaveCount(1)
    const hints = await collect(page)
    expect(hints).toHaveLength(n)
    for (const hint of hints) {
      expect(hint.trim()).not.toBe('')
      expect(hint.split(/\s+/).length, hint).toBeLessThanOrEqual(10)
      expect(hint, hint).not.toMatch(/\.$/)
    }
  })
}

const openTab = async (page: Page, tab: string) => {
  await page.getByTestId(`tab-${tab}`).click()
  await settle(page)
}

const select = async (page: Page, row: string, detail: string) => {
  const first = page.getByTestId(row).first()
  await first.click()
  await expect(first).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId(detail)).toBeVisible()
  await settle(page)
}

test('home', async ({ page }) => {
  await visit(page, '/')
  await expect(page.getByTestId('goals-table')).toBeVisible()
  await expect(page.getByTestId('findings-table')).toBeVisible()
  await audit(page, 'home')
})

test('activity', async ({ page }) => {
  await visit(page, '/activity')
  await expect(page.getByTestId('activity-table')).toBeVisible()
  await audit(page, 'activity')
})

test('metrics', async ({ page }) => {
  await page.route('**/api/metrics/history/*', (r) => r.fulfill({ json: series(r) }))
  await visit(page, '/metrics')
  await expect(page.getByTestId('metrics-table')).toBeVisible()
  await audit(page, 'metrics')
  await select(page, 'metrics-row', 'series-table')
  await audit(page, 'metrics series')
})

test('entities', async ({ page }) => {
  test.slow()
  await mockCandidates(page)
  await visit(page, '/entities')
  await expect(page.getByTestId('entities-table')).toBeVisible()
  await audit(page, 'entities canonical')
  await select(page, 'entities-row', 'detail-facts')
  await audit(page, 'entities canonical selected')
  await openTab(page, 'raw')
  await expect(page.getByTestId('records-table')).toBeVisible()
  await audit(page, 'entities raw')
  await select(page, 'records-row', 'record-events')
  await audit(page, 'entities raw selected')
  await openTab(page, 'visualize')
  await expect(page.getByTestId('visualize-table')).toBeVisible()
  await audit(page, 'entities visualize')
  await openTab(page, 'review')
  await expect(page.getByTestId('review-table')).toBeVisible()
  await audit(page, 'entities review')
})

test('ai', async ({ page }) => {
  await enable(page, '**/api/enrichment/vocabulary')
  await enable(page, '**/api/coaching')
  await visit(page, '/ai')
  await expect(page.getByTestId('facts-table')).toBeVisible()
  await audit(page, 'ai enrichment')
  await openTab(page, 'coaching')
  await expect(page.getByTestId('coaching-journal')).toBeVisible()
  await audit(page, 'ai coaching')
})

test('definitions', async ({ page }) => {
  test.slow()
  await visit(page, '/definitions')
  for (const [tab, tables] of Object.entries(DEFINITIONS)) {
    await openTab(page, tab)
    for (const table of tables) await expect(page.getByTestId(table)).toBeVisible()
    await audit(page, `definitions ${tab}`)
  }
})

test('config', async ({ page }) => {
  test.slow()
  await mockJson(page, '**/api/mcp', MCP)
  await visit(page, '/config')
  await expect(page.getByTestId('sources-table')).toBeVisible()
  await audit(page, 'config sources')
  await openTab(page, 'rebuild')
  await expect(page.getByTestId('rebuild-runs-table')).toBeVisible()
  await expect(page.getByTestId('rebuild-totals').locator('th').first()).toHaveText(/^Total \(\d+\)$/)
  await expect(page.getByTestId('rebuild-receipts')).toBeVisible()
  await audit(page, 'config rebuild')
  await openTab(page, 'mcp')
  for (const table of ['mcp-tools', 'mcp-resources', 'mcp-prompts']) await expect(page.getByTestId(table)).toBeVisible()
  await audit(page, 'config mcp')
})

test('search', async ({ page }) => {
  await visit(page, '/search?q=wayne')
  await expect(page.getByTestId('search-table')).toBeVisible()
  await audit(page, 'search')
})

test('hover shows the hint', async ({ page }) => {
  await visit(page, '/metrics')
  await page.getByTestId('metrics-table').locator('[data-testid=hint][aria-label="How many things were counted"]').hover()
  const tooltip = page.locator('[role=tooltip]')
  await expect(tooltip).toBeVisible()
  await expect(tooltip).toHaveText('How many things were counted')
  await snap(page, 'metrics-hint')
})
