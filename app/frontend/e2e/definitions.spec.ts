import type { Page } from '@playwright/test'
import { expect, mockJson, openSelect, snap, test, visit } from './fixtures'

const counted = (page: Page, label: string) =>
  page.getByRole('columnheader', { name: new RegExp(`^${label} \\(\\d[\\d,]*\\)$`) })

const closeSelect = async (page: Page) => {
  await page.keyboard.press('Escape')
  await expect(page.locator('[role=listbox]')).toHaveCount(0)
}

const openTab = async (page: Page, name: string) => {
  await visit(page, '/definitions')
  await page.getByRole('tab', { name }).click()
}

test('ontology', async ({ page }) => {
  await openTab(page, 'Ontology')
  await expect(page.getByRole('heading', { name: 'Source priority' })).toBeVisible()
  await expect(page.getByText('When sources disagree on an attribute, the most recently observed value wins.')).toBeVisible()
  await expect(counted(page, 'Entity')).toBeVisible()
  await expect(counted(page, 'Relationship')).toBeVisible()
  await expect(page.locator('td > span.rounded-full', { hasText: /^person$/ }).first()).toBeVisible()
  await snap(page, 'definitions-ontology')
})

test('mappings', async ({ page }) => {
  await openTab(page, 'Mappings')
  await expect(counted(page, 'Source')).toBeVisible()
  await expect(page.getByRole('combobox')).toHaveText(/^all sources \(\d[\d,]*\)$/)
  await snap(page, 'definitions-mappings')
})

test('mappings dropdown', async ({ page }) => {
  await openTab(page, 'Mappings')
  await expect(counted(page, 'Source')).toBeVisible()
  await openSelect(page, 'all sources')
  await snap(page, 'definitions-mappings-open')
  await closeSelect(page)
  await openSelect(page, 'all sources')
  const first = page.getByRole('option').nth(1)
  const name = (await first.innerText()).trim()
  const count = name.match(/\((\d[\d,]*)\)$/)![1]
  await first.click()
  await expect(page.locator('[role=listbox]')).toHaveCount(0)
  await expect(page.getByRole('combobox')).toHaveText(name)
  await expect(page.getByRole('columnheader', { name: `Source (${count})`, exact: true })).toBeVisible()
  await snap(page, 'definitions-mappings-filtered')
})

test('mappings scrolled keeps tab strip pinned', async ({ page }) => {
  await openTab(page, 'Mappings')
  await expect(counted(page, 'Source')).toBeVisible()
  const strip = page.getByRole('tablist')
  const top = (await strip.boundingBox())!.y
  const scrolled = await page.getByRole('table').evaluate((el) => {
    let node = el.parentElement
    while (node && node.scrollHeight <= node.clientHeight) node = node.parentElement
    if (!node) return -1
    node.scrollTop = 400
    return node.scrollTop
  })
  expect(scrolled).toBe(400)
  expect((await strip.boundingBox())!.y).toBe(top)
  await snap(page, 'definitions-mappings-scrolled')
})

test('transforms', async ({ page }) => {
  await openTab(page, 'Transforms')
  await expect(counted(page, 'Label')).toBeVisible()
  await expect(counted(page, 'Function')).toBeVisible()
  await snap(page, 'definitions-transforms')
})

test('transforms pager', async ({ page }) => {
  await openTab(page, 'Transforms')
  await expect(counted(page, 'Label')).toBeVisible()
  const next = page.getByRole('button', { name: 'Next →' })
  await expect(next).toBeEnabled()
  const firstLabel = page.locator('tbody tr td:first-child').first()
  const before = await firstLabel.innerText()
  await next.click()
  await expect(firstLabel).not.toHaveText(before)
  await expect(page.getByRole('button', { name: '← Prev' })).toBeEnabled()
  await snap(page, 'definitions-transforms-page-2')
})

test('metrics', async ({ page }) => {
  await openTab(page, 'Metrics')
  await expect(counted(page, 'Metric')).toBeVisible()
  await snap(page, 'definitions-metrics')
})

test('rules', async ({ page }) => {
  await openTab(page, 'Rules')
  await expect(counted(page, 'Rule')).toBeVisible()
  await snap(page, 'definitions-rules')
})

test('goals', async ({ page }) => {
  await openTab(page, 'Goals')
  await expect(counted(page, 'Goal')).toBeVisible()
  await snap(page, 'definitions-goals')
})

test('enrichment', async ({ page }) => {
  await openTab(page, 'Enrichment')
  await expect(counted(page, 'Reading')).toBeVisible()
  await snap(page, 'definitions-enrichment')
})

test('error', async ({ page }) => {
  await mockJson(page, '**/api/knowledge/*', { detail: 'knowledge unavailable' }, 500)
  await visit(page, '/definitions')
  const banner = page.getByRole('alert')
  await expect(banner).toContainText('500')
  await expect(banner).toContainText('knowledge unavailable')
  await snap(page, 'definitions-error')
})
