import type { Page } from '@playwright/test'
import { expect, mockJson, openSelect, snap, test, visit } from './fixtures'

const body = (page: Page) => page.locator('[class~="lg:overflow-y-auto"]')

test('default', async ({ page }) => {
  await visit(page, '/activity')
  await expect(page.getByRole('columnheader', { name: /^Entity \([\d,]+\)$/ })).toBeVisible()
  for (const name of ['Type', 'Changes', 'Source', 'When']) await expect(page.getByRole('columnheader', { name, exact: true })).toBeVisible()
  await snap(page, 'activity-default')
})

test('type filter open', async ({ page }) => {
  await visit(page, '/activity')
  await openSelect(page, 'all types')
  await expect(page.getByRole('option', { name: /^all types/ })).toBeVisible()
  await snap(page, 'activity-type-open')
  await page.keyboard.press('Escape')
  await expect(page.locator('[role=listbox]')).toHaveCount(0)
})

test('filtered by source', async ({ page }) => {
  await visit(page, '/activity')
  await openSelect(page, 'all sources')
  const option = page.getByRole('option').nth(1)
  const source = (await option.innerText()).trim().replace(/ \([\d,]+\)$/, '')
  await option.click()
  const sources = page.locator('tbody td:nth-child(4)')
  await expect(sources.first()).toHaveText(source)
  await expect(sources.filter({ hasNotText: source })).toHaveCount(0)
  await snap(page, 'activity-filtered-source')
})

test('page 2 starts at the top', async ({ page }) => {
  await visit(page, '/activity')
  const next = page.getByRole('button', { name: 'Next →' })
  test.skip(!(await next.count()) || !(await next.isEnabled()), 'activity fits on one page')
  await next.click()
  await expect(page.getByRole('button', { name: '← Prev' })).toBeEnabled()
  await expect.poll(() => body(page).evaluate((el) => el.scrollTop)).toBe(0)
  await snap(page, 'activity-page-2')
})

test('scrolled keeps the header pinned', async ({ page }) => {
  await visit(page, '/activity')
  const scroller = body(page)
  await scroller.evaluate((el) => {
    el.scrollTop = 300
  })
  await expect.poll(() => scroller.evaluate((el) => el.scrollTop)).toBe(300)
  const [head, top] = await Promise.all([page.locator('th').first().boundingBox(), scroller.boundingBox()])
  expect(head!.y).toBeCloseTo(top!.y, 0)
  await snap(page, 'activity-scrolled')
})

test('empty', async ({ page }) => {
  await mockJson(page, '**/api/activity*', { events: [] })
  await visit(page, '/activity')
  await expect(page.getByText('no activity yet')).toBeVisible()
  await snap(page, 'activity-empty')
})
