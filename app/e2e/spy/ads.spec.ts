import { expect, snap, test, visit } from '../fixtures'
import { ready } from '../dashboard/ready'

test('ads', async ({ page }) => {
  await visit(page, '/ads')
  await expect(page.getByTestId('subnav-all')).toHaveAttribute('aria-current', 'page')
  await expect(page.getByTestId('sub-nav').locator('a')).toHaveCount(2)
  await expect(page.getByTestId('ads-company').first()).toHaveAttribute('data-state', 'ready', { timeout: 20_000 })
  const cards = page.getByTestId('ad-card')
  await expect(cards.first()).toBeVisible()
  await expect(cards.locator('a').first()).toHaveAttribute('target', '_blank')
  await expect(cards.locator('a:not([target="_blank"])')).toHaveCount(0)
  await ready(page)
  await snap(page, 'spy-ads')
  await visit(page, '/ads/google')
  await expect(page.getByTestId('subnav-google')).toHaveAttribute('aria-current', 'page')
  await ready(page)
  await snap(page, 'spy-ads-google')
})
