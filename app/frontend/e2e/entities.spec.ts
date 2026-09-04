import type { Locator, Page } from '@playwright/test'
import { expect, mockJson, openSelect, settle, snap, test, visit } from './fixtures'

const counted = (page: Page, label: string) =>
  page.getByRole('columnheader', { name: new RegExp(`^${label} \\(\\d[\\d,]*\\)$`) })

const header = (page: Page, name: string) => page.getByRole('columnheader', { name, exact: true })

const rows = (page: Page) => page.locator('tbody tr')

const firstLine = async (cell: Locator) => (await cell.innerText()).split('\n')[0].trim()

const closeSelect = async (page: Page) => {
  await page.keyboard.press('Escape')
  await expect(page.locator('[role=listbox]')).toHaveCount(0)
}

const openTab = async (page: Page, name: string) => {
  await visit(page, '/entities')
  await page.getByRole('tab', { name }).click()
}

test('canonical default', async ({ page }) => {
  await visit(page, '/entities')
  for (const name of ['Canonical', 'Raw entities', 'Visualize']) await expect(page.getByRole('tab', { name })).toBeVisible()
  await expect(counted(page, 'Entity')).toBeVisible()
  await expect(header(page, 'Anchor')).toBeVisible()
  await expect(header(page, 'Sources')).toBeVisible()
  await expect(page.getByText('select an entity')).toBeVisible()
  await snap(page, 'entities-canonical-default')
})

test('canonical type dropdown open', async ({ page }) => {
  await visit(page, '/entities')
  await openSelect(page, 'all types')
  await expect(page.getByRole('option', { name: /^person \(\d+\)$/ })).toBeVisible()
  await snap(page, 'entities-canonical-type-open')
  await closeSelect(page)
})

test('canonical filtered to person', async ({ page }) => {
  await visit(page, '/entities')
  await openSelect(page, 'all types')
  await page.getByRole('option', { name: /^person \(\d+\)$/ }).click()
  await expect(page.locator('[role=listbox]')).toHaveCount(0)
  const types = rows(page).locator('td:first-child')
  await expect(types.filter({ hasNotText: /^person$/ })).toHaveCount(0)
  await expect(types.first()).toHaveText('person')
  await snap(page, 'entities-canonical-person')
})

test('canonical entity selected', async ({ page }) => {
  await visit(page, '/entities')
  const row = rows(page).first()
  const label = await firstLine(row.locator('td').nth(1))
  await row.click()
  await expect(row).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('heading', { name: label, exact: true })).toBeVisible()
  await expect(counted(page, 'Source')).toBeVisible()
  await expect(counted(page, 'Fact')).toBeVisible()
  await expect(counted(page, 'Link').or(page.getByText('no links'))).toBeVisible()
  await settle(page)
  await snap(page, 'entities-canonical-selected')
})

test('canonical anchor form', async ({ page }) => {
  await visit(page, '/entities')
  await expect(page.getByRole('cell', { name: /^[a-z_]+<>[a-z_]+<>\S+$/ }).first()).toBeVisible()
})

test('raw default', async ({ page }) => {
  await openTab(page, 'Raw entities')
  await expect(counted(page, 'Source')).toBeVisible()
  for (const name of ['Source id', 'Source type', 'Entity']) await expect(header(page, name)).toBeVisible()
  await expect(page.getByText('select a record')).toBeVisible()
  await snap(page, 'entities-raw-default')
})

test('raw record selected', async ({ page }) => {
  await openTab(page, 'Raw entities')
  await expect(counted(page, 'Source')).toBeVisible()
  const row = rows(page).first()
  const sourceId = (await row.locator('td').nth(1).innerText()).trim()
  await row.click()
  await expect(row).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('heading', { name: sourceId, exact: true })).toBeVisible()
  await expect(counted(page, 'Fact')).toBeVisible()
  await expect(counted(page, 'Raw event')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Payload' })).toBeVisible()
  await snap(page, 'entities-raw-selected')
})

test('raw dropdowns open', async ({ page }) => {
  await openTab(page, 'Raw entities')
  await expect(counted(page, 'Source')).toBeVisible()
  await openSelect(page, 'all types')
  await expect(page.getByRole('option', { name: /^person \(\d+\)$/ })).toBeVisible()
  await snap(page, 'entities-raw-type-open')
  await closeSelect(page)
  await openSelect(page, 'all sources')
  await expect(page.getByRole('option', { name: 'hubspot' })).toBeVisible()
  await snap(page, 'entities-raw-source-open')
  await closeSelect(page)
})

test('visualize company', async ({ page }) => {
  await openTab(page, 'Visualize')
  await expect(header(page, 'Company (10)')).toBeVisible()
  await expect(page.getByRole('button', { name: /^company \d+$/, pressed: true })).toBeVisible()
  await expect(page.getByRole('img', { name: 'Knowledge graph' })).toBeVisible()
  await snap(page, 'entities-visualize-company')
})

test('visualize person', async ({ page }) => {
  await openTab(page, 'Visualize')
  await expect(header(page, 'Company (10)')).toBeVisible()
  await page.getByRole('button', { name: /^person \d+$/ }).click()
  await expect(header(page, 'Person (23)')).toBeVisible()
  await expect(page.getByRole('button', { name: /^person \d+$/, pressed: true })).toBeVisible()
  await snap(page, 'entities-visualize-person')
})

test('visualize node selected', async ({ page }) => {
  await openTab(page, 'Visualize')
  await expect(header(page, 'Company (10)')).toBeVisible()
  const row = rows(page).first()
  await row.click()
  await expect(row).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('button', { name: /→/ }).first()).toBeVisible()
  await snap(page, 'entities-visualize-selected')
})

test('canonical empty', async ({ page }) => {
  await mockJson(page, '**/api/entities*', { total: 0, limit: 500, offset: 0, by_type: {}, entities: [] })
  await visit(page, '/entities')
  await expect(page.getByText('no entities')).toBeVisible()
  await expect(page.getByRole('combobox')).toHaveText('all types (0)')
  await snap(page, 'entities-canonical-empty')
})
