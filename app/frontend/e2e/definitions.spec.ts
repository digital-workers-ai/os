import type { Locator, Page } from '@playwright/test'
import { expect, mockJson, openFilter, pickOption, snap, test, visit } from './fixtures'

const counted = (scope: Locator, label: string) =>
  scope.getByRole('columnheader', { name: new RegExp(`^${label} \\(\\d[\\d,]*\\)$`) })

const table = (page: Page, card: string) => page.getByTestId(`${card}-table`)

const closeFilter = async (page: Page, filter: string) => {
  await page.keyboard.press('Escape')
  await expect(page.getByTestId(`${filter}-option`)).toHaveCount(0)
}

const openTab = async (page: Page, tab: string) => {
  await visit(page, '/definitions')
  await page.getByTestId(`tab-${tab}`).click()
}

test('ontology', async ({ page }) => {
  await openTab(page, 'ontology')
  await expect(page.getByTestId('source-priority-title')).toHaveText('Source priority')
  await expect(page.getByTestId('source-priority-description')).toContainText(
    'When sources disagree on an attribute, the most recently observed value wins.',
  )
  await expect(counted(table(page, 'definitions-ontology'), 'Entity')).toBeVisible()
  await expect(counted(table(page, 'definitions-relationships'), 'Relationship')).toBeVisible()
  await expect(table(page, 'definitions-ontology').getByText('person', { exact: true }).first()).toBeVisible()
  await snap(page, 'definitions-ontology')
})

test('mappings', async ({ page }) => {
  await openTab(page, 'mappings')
  await expect(counted(table(page, 'definitions-mappings'), 'Source')).toBeVisible()
  await expect(page.getByTestId('mappings-source-filter')).toHaveText(/^all sources \(\d[\d,]*\)$/)
  await snap(page, 'definitions-mappings')
})

test('mappings dropdown', async ({ page }) => {
  await openTab(page, 'mappings')
  await expect(counted(table(page, 'definitions-mappings'), 'Source')).toBeVisible()
  await openFilter(page, 'mappings-source-filter')
  await snap(page, 'definitions-mappings-open')
  const first = page.getByTestId('mappings-source-filter-option').nth(1)
  const name = (await first.innerText()).trim()
  const value = (await first.getAttribute('data-value'))!
  const count = name.match(/\((\d[\d,]*)\)$/)![1]
  await closeFilter(page, 'mappings-source-filter')
  await pickOption(page, 'mappings-source-filter', value)
  await expect(page.getByTestId('mappings-source-filter')).toHaveText(name)
  await expect(table(page, 'definitions-mappings').getByRole('columnheader', { name: `Source (${count})`, exact: true })).toBeVisible()
  await snap(page, 'definitions-mappings-filtered')
})

test('mappings scrolled keeps tab strip pinned', async ({ page }) => {
  await openTab(page, 'mappings')
  await expect(counted(table(page, 'definitions-mappings'), 'Source')).toBeVisible()
  const strip = page.getByTestId('tab-mappings')
  const top = (await strip.boundingBox())!.y
  const body = page.getByTestId('definitions-mappings-body')
  await body.evaluate((el) => {
    el.scrollTop = 400
  })
  await expect(body).toHaveJSProperty('scrollTop', 400)
  expect((await strip.boundingBox())!.y).toBe(top)
  await snap(page, 'definitions-mappings-scrolled')
})

test('transforms', async ({ page }) => {
  await openTab(page, 'transforms')
  await expect(counted(table(page, 'definitions-transforms'), 'Label')).toBeVisible()
  await expect(counted(table(page, 'definitions-transforms-functions'), 'Function')).toBeVisible()
  await snap(page, 'definitions-transforms')
})

test('transforms pager', async ({ page }) => {
  await openTab(page, 'transforms')
  await expect(counted(table(page, 'definitions-transforms'), 'Label')).toBeVisible()
  const next = page.getByTestId('pager-next')
  await expect(next).toBeEnabled()
  const firstLabel = table(page, 'definitions-transforms').locator('tbody td').first()
  const before = await firstLabel.innerText()
  await next.click()
  await expect(firstLabel).not.toHaveText(before)
  await expect(page.getByTestId('pager-prev')).toBeEnabled()
  await snap(page, 'definitions-transforms-page-2')
})

test('metrics', async ({ page }) => {
  await openTab(page, 'metrics')
  await expect(counted(table(page, 'definitions-metrics'), 'Metric')).toBeVisible()
  await snap(page, 'definitions-metrics')
})

test('rules', async ({ page }) => {
  await openTab(page, 'rules')
  await expect(counted(table(page, 'definitions-rules'), 'Rule')).toBeVisible()
  await snap(page, 'definitions-rules')
})

test('goals', async ({ page }) => {
  await openTab(page, 'goals')
  await expect(counted(table(page, 'definitions-goals'), 'Goal')).toBeVisible()
  await snap(page, 'definitions-goals')
})

test('enrichment', async ({ page }) => {
  await openTab(page, 'enrichment')
  await expect(counted(table(page, 'definitions-enrichment'), 'Reading')).toBeVisible()
  await snap(page, 'definitions-enrichment')
})

test('error', async ({ page }) => {
  await mockJson(page, '**/api/knowledge/*', { detail: 'knowledge unavailable' }, 500)
  await visit(page, '/definitions')
  const banner = page.getByTestId('error-banner')
  await expect(banner).toContainText('500')
  await expect(banner).toContainText('knowledge unavailable')
  await snap(page, 'definitions-error')
})
