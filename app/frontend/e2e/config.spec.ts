import type { Locator, Page } from '@playwright/test'
import { expect, mockJson, openFilter, pickOption, settle, snap, test, visit } from './fixtures'

test.describe.configure({ mode: 'default' })

const AMPLITUDE_ENABLED = '/api/sources/amplitude/enabled'

const result = (source: string, extra: Record<string, unknown> = {}) => ({
  source,
  ok: true,
  rows_fetched: 120,
  rows_written: 118,
  rows_refused: 0,
  rows_colliding: 0,
  pages_read: 2,
  truncated: false,
  detail: null,
  ...extra,
})
const SYNC = {
  ok: 2,
  failed: 1,
  rows_written: 236,
  results: [
    result('activecampaign', { rows_refused: 2 }),
    result('amplitude', { ok: false, rows_fetched: 0, rows_written: 0, detail: 'token expired' }),
    result('calendly', { rows_colliding: 3 }),
  ],
}
const REBUILT = { ok: true, duration_ms: 1234, raw_events_read: 382, entities: 388, facts: 1488 }
const MCP = {
  path: '/mcp',
  tools: [
    { name: 'get_metrics', description: 'Metric series with current value and trend' },
    { name: 'get_goals', description: 'Goals with progress against target' },
    { name: 'get_findings', description: 'Rule findings, newest first' },
    { name: 'entity_counts', description: 'Entity counts per type' },
    { name: 'find_entities', description: 'Search entities by name or type' },
    { name: 'get_entity', description: 'One entity with its facts and links' },
    { name: 'slice_metric', description: 'Composes a reviewed metric with a declared dimension, a time window, or one equality filter' },
  ],
  resources: ['ontology', 'mappings', 'transforms', 'synonyms', 'metrics', 'derived', 'rules', 'goals', 'enrichment'].map((name) => ({
    uri: `definitions://${name}`,
    name,
    description: `Committed ${name} definitions`,
  })),
  prompts: [
    { name: 'briefing_ceo', description: 'CEO briefing from the current estate' },
    { name: 'briefing_head_of_sales', description: 'Head of Sales briefing from the current estate' },
  ],
}

const sourceRow = (page: Page, source: string) => page.locator(`[data-testid="sources-row"][data-source="${source}"]`)
const enabledChips = (page: Page) => page.getByTestId('sources-table').locator('[data-testid^="source-enabled-"]')
const options = (page: Page) => page.getByTestId('sources-enabled-filter-option')
const heads = (table: Locator) => table.locator('th')
const runs = (page: Page) => page.getByTestId('rebuild-run')
const chips = (page: Page) => page.getByTestId('rebuild-status').locator(':scope > span')
const receiptsTitle = (page: Page) => page.getByTestId('rebuild-receipts-title')

const scroll = async (box: Locator, top: number) => {
  await box.evaluate((el, top) => (el.scrollTop = top), top)
  await expect(box).toHaveJSProperty('scrollTop', top)
}

const expectInHeader = async (page: Page, testId: string) => {
  await expect(page.getByTestId('sources-description').getByTestId(testId)).toHaveCount(1)
  await expect(page.getByTestId('sources-body').getByTestId(testId)).toHaveCount(0)
}

const openRebuild = async (page: Page) => {
  await visit(page, '/config')
  await page.getByTestId('tab-rebuild').click()
  await settle(page)
}

const openMcp = async (page: Page) => {
  await visit(page, '/config')
  await page.getByTestId('tab-mcp').click()
  await settle(page)
}

const restoreAmplitude = (page: Page) => page.request.put(AMPLITUDE_ENABLED, { data: { enabled: true } })

test('sources default', async ({ page }) => {
  await visit(page, '/config')
  await expect(heads(page.getByTestId('sources-table'))).toHaveText(['Source (27)', 'Entities', 'Last sync', 'Rows', 'Enabled', ''])
  await expect(page.getByTestId('sources-enabled-filter')).toHaveText('all sources (27)')
  await expect(enabledChips(page)).toHaveText(Array(27).fill('on'))
  await snap(page, 'config-sources-default')
})

test('filter open', async ({ page }) => {
  await visit(page, '/config')
  await openFilter(page, 'sources-enabled-filter')
  await expect(options(page)).toHaveText(['all sources (27)', 'enabled (27)', 'disabled (0)'])
  await snap(page, 'config-sources-filter-open')
  await page.keyboard.press('Escape')
  await expect(options(page)).toHaveCount(0)
})

test('toggle off', async ({ page }) => {
  await visit(page, '/config')
  const chip = page.getByTestId('source-enabled-amplitude')
  const sync = page.getByTestId('source-sync-amplitude')
  try {
    await chip.click()
    await expect(chip).toHaveText('off')
    await expect(sync).toBeDisabled()
    await openFilter(page, 'sources-enabled-filter')
    await expect(options(page)).toHaveText(['all sources (27)', 'enabled (26)', 'disabled (1)'])
    await page.keyboard.press('Escape')
    await expect(options(page)).toHaveCount(0)
    await snap(page, 'config-sources-one-off')
    await chip.click()
    await expect(chip).toHaveText('on')
    await expect(sync).toBeEnabled()
  } finally {
    await restoreAmplitude(page)
  }
})

test('filter disabled', async ({ page }) => {
  await visit(page, '/config')
  const chip = page.getByTestId('source-enabled-amplitude')
  try {
    await chip.click()
    await expect(chip).toHaveText('off')
    await pickOption(page, 'sources-enabled-filter', 'disabled')
    await expect(heads(page.getByTestId('sources-table')).first()).toHaveText('Source (1)')
    await expect(enabledChips(page)).toHaveText(['off'])
    await snap(page, 'config-sources-filtered-disabled')
    await chip.click()
    await expect(page.getByTestId('sources').getByTestId('empty')).toHaveText('no sources')
  } finally {
    await restoreAmplitude(page)
  }
})

test('sync all banner', async ({ page }) => {
  await mockJson(page, '**/api/sync', SYNC)
  await visit(page, '/config')
  await page.getByTestId('sync-all').click()
  await settle(page)
  const banner = page.getByTestId('sync-banner')
  await expect(banner).toContainText('synced 3 sources · 240 fetched · 236 written · 2 refused · 3 colliding')
  await expect(banner).toContainText('amplitude: token expired')
  await expectInHeader(page, 'sync-banner')
  await expect(sourceRow(page, 'amplitude')).toContainText('0 written / 0 fetched')
  await expect(sourceRow(page, 'activecampaign')).toContainText('2 refused')
  await expect(sourceRow(page, 'calendly')).toContainText('3 colliding')
  await snap(page, 'config-sources-sync-banner')
})

test('rebuild banner', async ({ page }) => {
  await mockJson(page, '**/api/rebuild', REBUILT)
  await visit(page, '/config')
  const rebuild = page.getByTestId('rebuild')
  await rebuild.click()
  const rebuilt = page.getByTestId('rebuild-banner')
  await expect(rebuilt).toHaveText('rebuilt · 1,234 ms · 382 raw events · 388 entities · 1,488 facts')
  await expectInHeader(page, 'rebuild-banner')
  await snap(page, 'config-sources-rebuild-banner')

  await mockJson(page, '**/api/rebuild', { detail: 'a rebuild is already in progress' }, 409)
  await rebuild.click()
  await expect(page.getByTestId('rebuild-error')).toHaveText('409 rebuild in progress — a rebuild is already in progress')
  await expectInHeader(page, 'rebuild-error')
  await expect(rebuilt).toBeVisible()
  await snap(page, 'config-sources-rebuild-409')
})

test('sources error', async ({ page }) => {
  await mockJson(page, '**/api/sources', { detail: 'sources table missing' }, 500)
  await visit(page, '/config')
  await expect(page.getByTestId('sources-body').getByTestId('error-banner')).toHaveText('500 sources table missing')
  await expect(page.getByTestId('sync-all')).toBeDisabled()
  await expect(page.getByTestId('sources-table')).toHaveCount(0)
  await snap(page, 'config-sources-error')
})

test('rebuild tab default', async ({ page }) => {
  await openRebuild(page)
  await expect(heads(page.getByTestId('rebuild-runs-table'))).toHaveText([/^Rebuild \(\d+\)$/, 'Status', 'Duration', 'Issues'])
  await expect(runs(page).first()).toHaveAttribute('data-state', 'selected')
  await expect(page.locator('[data-testid="rebuild-run"][data-state="selected"]')).toHaveCount(1)
  await expect(chips(page)).toHaveText(['ok', /^ran \d+[smhd] ago$/, /^duration [\d,]+ ms$/, /^raw events [\d,]+$/, /^entities [\d,]+$/, /^facts [\d,]+$/])
  await expect(heads(page.getByTestId('rebuild-totals')).first()).toHaveText('Total (10)')
  await expect(receiptsTitle(page)).toHaveText('Receipts')
  await snap(page, 'config-rebuild-default')
})

test('second run selected', async ({ page }) => {
  await openRebuild(page)
  const rows = runs(page)
  const duration = chips(page).filter({ hasText: 'duration' })
  const before = await duration.textContent()
  await rows.nth(1).click()
  await settle(page)
  await expect(rows.nth(1)).toHaveAttribute('data-state', 'selected')
  await expect(rows.first()).not.toHaveAttribute('data-state', 'selected')
  await expect(duration).not.toHaveText(before!)
  await expect(duration).toHaveText(`duration ${await rows.nth(1).locator('td').nth(2).textContent()}`)
  await snap(page, 'config-rebuild-second')
})

test('no runs', async ({ page }) => {
  await mockJson(page, '**/api/report/runs*', { runs: [] })
  await openRebuild(page)
  await expect(page.getByTestId('rebuild-runs').getByTestId('empty')).toHaveText('no rebuild has run yet')
  await expect(page.getByTestId('rebuild-receipts')).toHaveCount(0)
  await snap(page, 'config-rebuild-empty')
})

test('rebuild scrolled', async ({ page }) => {
  await openRebuild(page)
  await expect(receiptsTitle(page)).toBeVisible()
  await scroll(page.getByTestId('rebuild-receipt'), 300)
  await expect(heads(page.getByTestId('rebuild-runs-table')).first()).toBeInViewport()
  await snap(page, 'config-rebuild-scrolled')
})

test('mcp tab', async ({ page }) => {
  await mockJson(page, '**/api/mcp', MCP)
  await openMcp(page)
  const endpoint = `${new URL(page.url()).origin}/mcp`
  await expect(page.getByTestId('mcp-title')).toHaveText(endpoint)
  await expect(page.getByTestId('mcp-copy')).toHaveText('Copy')
  await expect(heads(page.getByTestId('mcp-tools'))).toHaveText(['Tool (7)', 'Description'])
  await expect(heads(page.getByTestId('mcp-resources'))).toHaveText(['Resource (9)', 'URI', 'Description'])
  await expect(heads(page.getByTestId('mcp-prompts'))).toHaveText(['Prompt (2)', 'Description'])
  const blocks = page.getByTestId('mcp-client-body').locator('pre')
  await expect(blocks).toHaveCount(2)
  await expect(blocks.nth(0)).toHaveText(`claude mcp add --transport http os ${endpoint}`)
  await expect(blocks.nth(1)).toContainText(`"url": "${endpoint}"`)
  await snap(page, 'config-mcp')
})

test('mcp error', async ({ page }) => {
  await mockJson(page, '**/api/mcp', { detail: 'mcp index unavailable' }, 500)
  await openMcp(page)
  await expect(page.getByTestId('mcp-body').getByTestId('error-banner')).toHaveText('500 mcp index unavailable')
  await expect(page.getByTestId('mcp-tools')).toHaveCount(0)
  await expect(page.getByTestId('mcp-client')).toHaveCount(0)
  await snap(page, 'config-mcp-error')
})
