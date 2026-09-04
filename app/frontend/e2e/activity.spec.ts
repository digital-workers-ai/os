import { expect, mockJson, openFilter, snap, test, visit } from './fixtures'

test('default', async ({ page }) => {
  await visit(page, '/activity')
  const table = page.getByTestId('activity-table')
  await expect(table.getByRole('columnheader', { name: /^Entity \([\d,]+\)$/ })).toBeVisible()
  for (const name of ['Type', 'Changes', 'Source', 'When']) await expect(table.getByRole('columnheader', { name, exact: true })).toBeVisible()
  await snap(page, 'activity-default')
})

test('type filter open', async ({ page }) => {
  await visit(page, '/activity')
  await openFilter(page, 'activity-type-filter')
  await expect(page.locator('[data-testid="activity-type-filter-option"][data-value="*"]')).toHaveText(/^all types/)
  await snap(page, 'activity-type-open')
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('activity-type-filter-option')).toHaveCount(0)
})

test('filtered by source', async ({ page }) => {
  await visit(page, '/activity')
  await openFilter(page, 'activity-source-filter')
  const option = page.getByTestId('activity-source-filter-option').nth(1)
  const source = (await option.getAttribute('data-value'))!
  await option.click()
  const sources = page.getByTestId('activity-table').locator('tbody td:nth-child(4)')
  await expect(sources.first()).toHaveText(source)
  await expect(sources.filter({ hasNotText: source })).toHaveCount(0)
  await snap(page, 'activity-filtered-source')
})

test('page 2 starts at the top', async ({ page }) => {
  await visit(page, '/activity')
  const card = page.getByTestId('activity')
  const next = card.getByTestId('pager-next')
  test.skip(!(await next.count()) || !(await next.isEnabled()), 'activity fits on one page')
  await next.click()
  await expect(card.getByTestId('pager-prev')).toBeEnabled()
  await expect.poll(() => page.getByTestId('activity-body').evaluate((el) => el.scrollTop)).toBe(0)
  await snap(page, 'activity-page-2')
})

test('scrolled keeps the header pinned', async ({ page }) => {
  await visit(page, '/activity')
  const scroller = page.getByTestId('activity-body')
  await scroller.evaluate((el) => {
    el.scrollTop = 300
  })
  await expect.poll(() => scroller.evaluate((el) => el.scrollTop)).toBe(300)
  const [head, top] = await Promise.all([page.getByTestId('activity-table').locator('th').first().boundingBox(), scroller.boundingBox()])
  expect(head!.y).toBeCloseTo(top!.y, 0)
  await snap(page, 'activity-scrolled')
})

test('empty', async ({ page }) => {
  await mockJson(page, '**/api/activity*', { events: [] })
  await visit(page, '/activity')
  await expect(page.getByTestId('activity').getByTestId('empty')).toHaveText('no activity yet')
  await snap(page, 'activity-empty')
})
