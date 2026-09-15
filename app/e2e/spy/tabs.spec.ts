import { expect, snap, test, visit } from '../fixtures'
import { ready } from './ready'

const TABS = [
  ['meta-ads', 'Meta ads'],
  ['google-ads', 'Google ads'],
  ['search', 'Search'],
  ['answers', 'AI answers'],
  ['pages', 'Pages'],
  ['linkedin', 'LinkedIn'],
] as const

const SOURCE_LINE = /^[a-z_]+$/

test('nav tabs', async ({ page }) => {
  await visit(page, '/')
  await expect(page).toHaveURL(/\/meta-ads$/)
  await expect(page.getByTestId('top-nav').locator('nav a')).toHaveText(TABS.map(([, label]) => label))
  for (const [slug] of TABS) await expect(page.getByTestId(`nav-${slug}`)).toBeVisible()
})

for (const [slug, label] of TABS) {
  test(label, async ({ page }) => {
    await visit(page, `/${slug}`)
    await ready(page)
    await expect(page.getByTestId(`nav-${slug}`)).toHaveAttribute('aria-current', 'page')
    await expect(page.getByTestId(`view-${slug}`)).toBeVisible()
    await expect(page.getByTestId('source-line')).toHaveText(SOURCE_LINE)
    await expect(page.getByTestId('spy-table').first().locator('tbody tr').first()).toBeVisible()
    await snap(page, `spy-${slug}`)
  })
}
