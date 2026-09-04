import type { Locator, Page } from '@playwright/test'
import { expect, mockJson, openFilter, pickOption, settle, snap, test, visit } from './fixtures'

const TABS = { canonical: 'Canonical', raw: 'Raw entities', visualize: 'Visualize' }

const counted = (scope: Locator, label: string) =>
  scope.getByRole('columnheader', { name: new RegExp(`^${label} \\(\\d[\\d,]*\\)$`) })

const header = (scope: Locator, name: string) => scope.getByRole('columnheader', { name, exact: true })

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
  await snap(page, 'entities-raw-selected')
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
  await expect(header(table, 'Person (23)')).toBeVisible()
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
