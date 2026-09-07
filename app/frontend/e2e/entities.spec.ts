import type { Locator, Page } from '@playwright/test'
import { CANDIDATES, expect, header, mockCandidates, mockJson, openFilter, pickOption, settle, snap, test, visit } from './fixtures'

const TABS = { canonical: 'Canonical', raw: 'Raw entities', visualize: 'Visualize', review: 'Review' }

const counted = (scope: Locator, label: string) => header(scope, new RegExp(`^${label} \\(\\d[\\d,]*\\)$`))

const option = (page: Page, filter: string, value: string) =>
  page.locator(`[data-testid="${filter}-option"][data-value="${value}"]`)

const firstLine = async (cell: Locator) => (await cell.innerText()).split('\n')[0].trim()

const closeFilter = async (page: Page, filter: string) => {
  await page.keyboard.press('Escape')
  await expect(page.getByTestId(`${filter}-option`)).toHaveCount(0)
}

const openTab = async (page: Page, tab: keyof typeof TABS) => {
  await visit(page, '/entities')
  await page.getByTestId(`tab-${tab}`).click()
}

test('canonical default', async ({ page }) => {
  await visit(page, '/entities')
  for (const [tab, name] of Object.entries(TABS)) await expect(page.getByTestId(`tab-${tab}`)).toHaveText(name)
  const table = page.getByTestId('entities-table')
  await expect(counted(table, 'Entity')).toBeVisible()
  await expect(header(table, 'Anchor')).toBeVisible()
  await expect(header(table, 'Sources')).toBeVisible()
  await expect(page.getByTestId('entity-detail').getByTestId('empty')).toHaveText('select an entity')
  await snap(page, 'entities-canonical-default')
})

test('canonical type dropdown open', async ({ page }) => {
  await visit(page, '/entities')
  await openFilter(page, 'entities-type-filter')
  await expect(option(page, 'entities-type-filter', 'person')).toHaveText(/^person \(\d+\)$/)
  await snap(page, 'entities-canonical-type-open')
  await closeFilter(page, 'entities-type-filter')
})

test('canonical filtered to person', async ({ page }) => {
  await visit(page, '/entities')
  await pickOption(page, 'entities-type-filter', 'person')
  const types = page.getByTestId('entities-row').locator('td').first()
  await expect(types.filter({ hasNotText: /^person$/ })).toHaveCount(0)
  await expect(types.first()).toHaveText('person')
  await snap(page, 'entities-canonical-person')
})

test('canonical entity selected', async ({ page }) => {
  await visit(page, '/entities')
  const row = page.getByTestId('entities-row').first()
  const label = await firstLine(row.locator('td').nth(1))
  await row.click()
  await expect(row).toHaveAttribute('aria-selected', 'true')
  const detail = page.getByTestId('entity-detail')
  await expect(detail.getByTestId('entity-detail-title')).toHaveText(label)
  await expect(counted(page.getByTestId('detail-sources'), 'Source')).toBeVisible()
  await expect(counted(page.getByTestId('detail-facts'), 'Fact')).toBeVisible()
  await expect(
    counted(page.getByTestId('detail-links'), 'Link').or(detail.getByTestId('empty').filter({ hasText: 'no links' })),
  ).toBeVisible()
  await settle(page)
  await snap(page, 'entities-canonical-selected')
})

test('canonical anchor form', async ({ page }) => {
  await visit(page, '/entities')
  await expect(page.getByTestId('entities-table').getByRole('cell', { name: /^[a-z_]+<>[a-z_]+<>\S+$/ }).first()).toBeVisible()
})

test('raw default', async ({ page }) => {
  await openTab(page, 'raw')
  const table = page.getByTestId('records-table')
  await expect(counted(table, 'Source')).toBeVisible()
  for (const name of ['Source id', 'Source type', 'Entity']) await expect(header(table, name)).toBeVisible()
  await expect(page.getByTestId('record-detail').getByTestId('empty')).toHaveText('select a record')
  await snap(page, 'entities-raw-default')
})

test('raw record selected', async ({ page }) => {
  await openTab(page, 'raw')
  await expect(counted(page.getByTestId('records-table'), 'Source')).toBeVisible()
  const row = page.getByTestId('records-row').first()
  const sourceId = (await row.locator('td').nth(1).innerText()).trim()
  await row.click()
  await expect(row).toHaveAttribute('aria-selected', 'true')
  const detail = page.getByTestId('record-detail')
  await expect(detail.getByTestId('record-detail-title')).toHaveText(sourceId)
  await expect(counted(page.getByTestId('record-facts'), 'Fact')).toBeVisible()
  await expect(counted(page.getByTestId('record-events'), 'Raw event')).toBeVisible()
  await expect(detail.getByRole('heading', { name: 'Payload' })).toBeVisible()
  await expect(page.getByTestId('record-payload')).toBeVisible()
  await snap(page, 'entities-raw-selected', { mask: [page.getByTestId('record-events').locator('tbody td').first()] })
})

test('raw dropdowns open', async ({ page }) => {
  await openTab(page, 'raw')
  await expect(counted(page.getByTestId('records-table'), 'Source')).toBeVisible()
  await openFilter(page, 'records-type-filter')
  await expect(option(page, 'records-type-filter', 'person')).toHaveText(/^person \(\d+\)$/)
  await snap(page, 'entities-raw-type-open')
  await closeFilter(page, 'records-type-filter')
  await openFilter(page, 'records-source-filter')
  await expect(option(page, 'records-source-filter', 'hubspot')).toHaveText('hubspot')
  await snap(page, 'entities-raw-source-open')
  await closeFilter(page, 'records-source-filter')
})

test('visualize company', async ({ page }) => {
  await openTab(page, 'visualize')
  await expect(header(page.getByTestId('visualize-table'), 'Company (10)')).toBeVisible()
  const company = page.getByTestId('visualize-toggle-company')
  await expect(company).toHaveText(/^company \d+$/)
  await expect(company).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('visualize-canvas').getByRole('img', { name: 'Knowledge graph' })).toBeVisible()
  await snap(page, 'entities-visualize-company')
})

test('visualize person', async ({ page }) => {
  await openTab(page, 'visualize')
  const table = page.getByTestId('visualize-table')
  await expect(header(table, 'Company (10)')).toBeVisible()
  const person = page.getByTestId('visualize-toggle-person')
  await person.click()
  await expect(header(table, 'Person (28)')).toBeVisible()
  await expect(person).toHaveText(/^person \d+$/)
  await expect(person).toHaveAttribute('aria-pressed', 'true')
  await snap(page, 'entities-visualize-person')
})

test('visualize node selected', async ({ page }) => {
  await openTab(page, 'visualize')
  await expect(header(page.getByTestId('visualize-table'), 'Company (10)')).toBeVisible()
  const row = page.getByTestId('visualize-row').first()
  await row.click()
  await expect(row).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('visualize-selected').getByRole('button', { name: /→/ }).first()).toBeVisible()
  await snap(page, 'entities-visualize-selected')
})

test('canonical empty', async ({ page }) => {
  await mockJson(page, '**/api/entities*', { total: 0, limit: 500, offset: 0, by_type: {}, entities: [] })
  await visit(page, '/entities')
  await expect(page.getByTestId('entities').getByTestId('empty')).toHaveText('no entities')
  await expect(page.getByTestId('entities-type-filter')).toHaveText('all types (0)')
  await snap(page, 'entities-canonical-empty')
})

test('review default', async ({ page }) => {
  await mockCandidates(page)
  await openTab(page, 'review')
  const table = page.getByTestId('review-table')
  await expect(header(table, 'Pair (1)')).toBeVisible()
  for (const name of ['Entity', 'Evidence', 'Score', 'Status']) await expect(header(table, name)).toBeVisible()
  const row = page.getByTestId('review-row')
  await expect(row).toHaveCount(1)
  await expect(row).toHaveAttribute('data-seq', '1')
  await expect(row).toContainText('Carlos Ch')
  await expect(row).toContainText('C Chinchilla')
  await expect(row.getByTestId('review-confirm')).toHaveText('Confirm')
  await expect(row.getByTestId('review-reject')).toHaveText('Reject')
  await expect(page.getByTestId('review-status-filter')).toHaveText('pending (1)')
  await snap(page, 'entities-review-default')
})

test('review filter open', async ({ page }) => {
  await mockCandidates(page)
  await openTab(page, 'review')
  await expect(header(page.getByTestId('review-table'), 'Pair (1)')).toBeVisible()
  await openFilter(page, 'review-status-filter')
  await expect(option(page, 'review-status-filter', '*')).toHaveText('all (3)')
  for (const status of ['pending', 'confirmed', 'rejected']) {
    await expect(option(page, 'review-status-filter', status)).toHaveText(`${status} (1)`)
  }
  await snap(page, 'entities-review-filter-open')
  await closeFilter(page, 'review-status-filter')
})

test('review confirmed', async ({ page }) => {
  await mockCandidates(page)
  await openTab(page, 'review')
  await expect(header(page.getByTestId('review-table'), 'Pair (1)')).toBeVisible()
  await pickOption(page, 'review-status-filter', 'confirmed')
  const row = page.getByTestId('review-row')
  await expect(row).toHaveAttribute('data-seq', '2')
  await expect(row.getByText('evidence gone')).toBeVisible()
  await expect(row.getByTestId('review-unmerge')).toHaveText('Unmerge')
  await expect(row.getByTestId('review-confirm')).toHaveCount(0)
  await snap(page, 'entities-review-confirmed')
})

test('review confirm', async ({ page }) => {
  const candidates = CANDIDATES.map((c) => ({ ...c }))
  await mockCandidates(page, candidates)
  await page.route('**/api/resolution/candidates/1/confirm', (r) => {
    candidates[0].status = 'confirmed'
    return r.fulfill({ json: candidates[0] })
  })
  await openTab(page, 'review')
  await expect(page.getByTestId('review-row')).toHaveCount(1)
  await page.getByTestId('review-confirm').click()
  await expect(page.getByTestId('review').getByTestId('empty')).toHaveText('no pairs to review')
  await expect(page.getByTestId('review-row')).toHaveCount(0)
  await expect(page.getByTestId('review-status-filter')).toHaveText('pending (0)')
})

test('review 409', async ({ page }) => {
  await mockCandidates(page)
  await mockJson(page, '**/api/resolution/candidates/1/confirm', { detail: 'a rebuild is already in progress' }, 409)
  await openTab(page, 'review')
  await page.getByTestId('review-confirm').click()
  await expect(page.getByTestId('review-description').getByTestId('review-error')).toHaveText('409 a rebuild is already in progress')
  await expect(page.getByTestId('review-row')).toHaveCount(1)
  await expect(page.getByTestId('review-confirm')).toBeEnabled()
  await snap(page, 'entities-review-409')
})

test('review empty', async ({ page }) => {
  await mockCandidates(page, [])
  await openTab(page, 'review')
  await expect(page.getByTestId('review').getByTestId('empty')).toHaveText('no pairs to review')
  await expect(page.getByTestId('review-status-filter')).toHaveText('pending (0)')
  await snap(page, 'entities-review-empty')
})
