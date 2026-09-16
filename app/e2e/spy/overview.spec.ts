import { expect, snap, test, visit } from '../fixtures'
import { ready } from '../dashboard/ready'

const CARDS = ['brand_mention_rate', 'ai_overview_brand_mentions', 'brand_google_position', 'competitor_ads']

test('overview', async ({ page }) => {
  await visit(page, '/overview')
  const share = page.getByTestId('share-table')
  await expect(share).toHaveAttribute('data-state', 'ready', { timeout: 30_000 })
  for (const card of CARDS) await expect(page.getByTestId(`card-${card}`)).toBeVisible()
  await expect(share.locator('tbody tr').first()).toContainText('(you)')
  await expect(page.getByTestId('activity-list')).toBeVisible()
  await ready(page)
  await snap(page, 'spy-overview')
})
