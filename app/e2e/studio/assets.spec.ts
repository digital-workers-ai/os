import { expect, snap, test, visit } from '../fixtures'
import { ready } from './ready'

test('grid and filters', async ({ page }) => {
  await visit(page, '/assets')
  await ready(page)
  await expect(page.getByTestId('asset-card')).toHaveCount(6)
  await expect(page.getByTestId('assets-total')).toHaveText('6 assets')

  await page.getByTestId('assets-filter-kind').selectOption('image')
  await expect(page.getByTestId('asset-card')).toHaveCount(2)
  await expect(page.getByTestId('asset-card-preview')).toHaveCount(2)
  await page.getByTestId('assets-filter-kind').selectOption('')
  await expect(page.getByTestId('asset-card')).toHaveCount(6)

  await page.getByTestId('assets-search').fill('review')
  await expect(page.getByTestId('asset-card')).toHaveCount(1)
  await expect(page.getByTestId('asset-card-name')).toHaveText('The review queue this week')
  await page.getByTestId('assets-search').fill('')
  await expect(page.getByTestId('asset-card')).toHaveCount(6)

  await ready(page)
  await snap(page, 'studio-assets')
})

test('the held one', async ({ page }) => {
  await visit(page, '/assets')
  await ready(page)
  const held = page.locator('[data-testid="asset-card"]').filter({ has: page.getByTestId('status-pill') })
  await expect(held).toHaveCount(1)
  await expect(held.getByTestId('status-pill')).toHaveText('held')
  await held.click()
  await ready(page)
  await expect(page.getByTestId('asset-detail-view')).toHaveAttribute('data-state', 'ready')
  await expect(page.getByTestId('status-pill')).toHaveText('held')
  await expect(page.getByTestId('asset-claim').filter({ hasText: '✗' })).toHaveCount(1)
  await snap(page, 'studio-assets-held')
})
