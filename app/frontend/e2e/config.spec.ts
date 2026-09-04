import type { Locator, Page } from '@playwright/test'
import { expect, mockJson, openSelect, settle, snap, test, visit } from './fixtures'

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

const sourceRow = (page: Page, source: string) => page.locator('tbody tr', { hasText: source })
const enabledChip = (row: Locator) => row.getByRole('button', { name: /^(on|off)$/ })
const options = (page: Page) => page.getByRole('option')
const runs = (page: Page) => page.locator('table').first()
const chips = (page: Page) => page.locator('h3', { hasText: 'raw events' }).locator('span')
const scrollBox = (of: Locator) => of.locator('xpath=ancestor::*[contains(@class,"overflow-y-auto")][1]')

const scroll = async (box: Locator, top: number) => {
  await box.evaluate((el, top) => (el.scrollTop = top), top)
  await expect(box).toHaveJSProperty('scrollTop', top)
}

const above = async (a: Locator, b: Locator) => expect((await a.boundingBox())!.y).toBeLessThan((await b.boundingBox())!.y)

const openRebuild = async (page: Page) => {
  await visit(page, '/config')
  await page.getByRole('tab', { name: 'Rebuild' }).click()
  await settle(page)
}

const restoreAmplitude = (page: Page) => page.request.put(AMPLITUDE_ENABLED, { data: { enabled: true } })

test('sources default', async ({ page }) => {
  await visit(page, '/config')
  await expect(page.getByRole('columnheader')).toHaveText(['Source (27)', 'Entities', 'Last sync', 'Rows', 'Enabled', ''])
  await expect(page.getByRole('combobox')).toHaveText('all sources (27)')
  await expect(page.getByRole('button', { name: 'on', exact: true })).toHaveCount(27)
  await expect(page.getByRole('button', { name: 'off', exact: true })).toHaveCount(0)
  await snap(page, 'config-sources-default')
})

test('filter open', async ({ page }) => {
  await visit(page, '/config')
  await openSelect(page, 'all sources')
  await expect(options(page)).toHaveText(['all sources (27)', 'enabled (27)', 'disabled (0)'])
  await snap(page, 'config-sources-filter-open')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('listbox')).toHaveCount(0)
})

test('toggle off', async ({ page }) => {
  await visit(page, '/config')
  const row = sourceRow(page, 'amplitude')
  const chip = enabledChip(row)
  try {
    await chip.click()
    await expect(chip).toHaveText('off')
    await expect(row.getByRole('button', { name: 'Sync' })).toBeDisabled()
    await openSelect(page, 'all sources')
    await expect(options(page)).toHaveText(['all sources (27)', 'enabled (26)', 'disabled (1)'])
    await page.keyboard.press('Escape')
    await expect(page.getByRole('listbox')).toHaveCount(0)
    await snap(page, 'config-sources-one-off')
    await chip.click()
    await expect(chip).toHaveText('on')
    await expect(row.getByRole('button', { name: 'Sync' })).toBeEnabled()
  } finally {
    await restoreAmplitude(page)
  }
})

test('filter disabled', async ({ page }) => {
  await visit(page, '/config')
  const chip = enabledChip(sourceRow(page, 'amplitude'))
  try {
    await chip.click()
    await expect(chip).toHaveText('off')
    await openSelect(page, 'all sources')
    await options(page).filter({ hasText: 'disabled (1)' }).click()
    await expect(page.getByRole('columnheader').first()).toHaveText('Source (1)')
    await expect(page.getByRole('button', { name: 'off', exact: true })).toHaveCount(1)
    await snap(page, 'config-sources-filtered-disabled')
    await chip.click()
    await expect(page.getByText('no sources')).toBeVisible()
  } finally {
    await restoreAmplitude(page)
  }
})

test('sync all banner', async ({ page }) => {
  await mockJson(page, '**/api/sync', SYNC)
  await visit(page, '/config')
  await page.getByRole('button', { name: 'Sync all' }).click()
  await settle(page)
  const banner = page.getByRole('alert')
  await expect(banner).toContainText('synced 3 sources · 240 fetched · 236 written · 2 refused · 3 colliding')
  await expect(banner).toContainText('amplitude: token expired')
  await expect(scrollBox(banner)).toHaveCount(0)
  await above(banner, page.locator('table'))
  await expect(sourceRow(page, 'amplitude')).toContainText('0 written / 0 fetched')
  await expect(sourceRow(page, 'activecampaign')).toContainText('2 refused')
  await expect(sourceRow(page, 'calendly')).toContainText('3 colliding')
  await snap(page, 'config-sources-sync-banner')
})

test('rebuild banner', async ({ page }) => {
  await mockJson(page, '**/api/rebuild', REBUILT)
  await visit(page, '/config')
  const rebuild = page.getByRole('button', { name: 'Rebuild' })
  await rebuild.click()
  const rebuilt = page.getByRole('status').filter({ hasText: 'rebuilt' })
  await expect(rebuilt).toHaveText('rebuilt · 1,234 ms · 382 raw events · 388 entities · 1,488 facts')
  await above(rebuilt, page.locator('table'))
  await snap(page, 'config-sources-rebuild-banner')

  await mockJson(page, '**/api/rebuild', { detail: 'a rebuild is already in progress' }, 409)
  await rebuild.click()
  await expect(page.getByRole('status').filter({ hasText: '409' })).toHaveText('409 rebuild in progress — a rebuild is already in progress')
  await expect(rebuilt).toBeVisible()
  await snap(page, 'config-sources-rebuild-409')
})

test('sources error', async ({ page }) => {
  await mockJson(page, '**/api/sources', { detail: 'sources table missing' }, 500)
  await visit(page, '/config')
  await expect(page.getByRole('alert')).toHaveText('500 sources table missing')
  await expect(page.getByRole('button', { name: 'Sync all' })).toBeDisabled()
  await expect(page.locator('table')).toHaveCount(0)
  await snap(page, 'config-sources-error')
})

test('rebuild tab default', async ({ page }) => {
  await openRebuild(page)
  const list = runs(page)
  await expect(list.getByRole('columnheader')).toHaveText([/^Rebuild \(\d+\)$/, 'Status', 'Duration', 'Issues'])
  await expect(list.locator('tbody tr').first()).toHaveAttribute('aria-selected', 'true')
  await expect(list.locator('tbody tr[aria-selected=true]')).toHaveCount(1)
  await expect(chips(page)).toHaveText(['ok', /^ran \d+[smhd] ago$/, /^duration [\d,]+ ms$/, /^raw events [\d,]+$/, /^entities [\d,]+$/, /^facts [\d,]+$/])
  await expect(page.getByRole('columnheader', { name: 'Total (9)' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Receipts' })).toBeVisible()
  await snap(page, 'config-rebuild-default')
})

test('second run selected', async ({ page }) => {
  await openRebuild(page)
  const rows = runs(page).locator('tbody tr')
  const duration = chips(page).filter({ hasText: 'duration' })
  const before = await duration.textContent()
  await rows.nth(1).click()
  await settle(page)
  await expect(rows.nth(1)).toHaveAttribute('aria-selected', 'true')
  await expect(rows.first()).toHaveAttribute('aria-selected', 'false')
  await expect(duration).not.toHaveText(before!)
  await expect(duration).toHaveText(`duration ${await rows.nth(1).locator('td').nth(2).textContent()}`)
  await snap(page, 'config-rebuild-second')
})

test('no runs', async ({ page }) => {
  await mockJson(page, '**/api/report/runs*', { runs: [] })
  await openRebuild(page)
  await expect(page.getByText('no rebuild has run yet')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Receipts' })).toHaveCount(0)
  await snap(page, 'config-rebuild-empty')
})

test('rebuild scrolled', async ({ page }) => {
  await openRebuild(page)
  await scroll(scrollBox(page.getByRole('heading', { name: 'Receipts' })), 300)
  await expect(runs(page).getByRole('columnheader').first()).toBeInViewport()
  await snap(page, 'config-rebuild-scrolled')
})
