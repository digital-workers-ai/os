import { expect, snap, test, visit } from '../fixtures'

const PAGES = ['overview', 'visibility', 'ads', 'posts', 'competitors']

test('shell', async ({ page }) => {
  await visit(page, '/')
  await expect(page).toHaveURL(/\/overview$/)
  for (const name of PAGES) await expect(page.getByTestId(`nav-${name}`)).toBeVisible()
  await expect(page.locator('[data-state="loading"]')).toHaveCount(0, { timeout: 30_000 })
  await page.evaluate(() => window.scrollTo(0, 0))
  await snap(page, 'spy-shell')
})
