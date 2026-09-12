import { expect, mockJson, NOW, snap, test, visit } from '../fixtures'
import { ready } from './ready'

const EMPTY = {
  as_of: NOW.toISOString(),
  metric: 'sessions',
  label: 'Sessions',
  entity: 'traffic_report',
  value: 0,
  entities: 0,
  raw_fields: [],
  attrs: [],
}

test('all zero', async ({ page }) => {
  await mockJson(page, '**/api/metrics/*', EMPTY)
  await visit(page, '/')
  const banner = page.getByTestId('empty-page')
  await expect(banner).toContainText('No data for this page yet')
  await expect(banner.locator('a')).toHaveAttribute('href', /\/config\/sources$/)
  await ready(page)
  await snap(page, 'dashboard-empty')
})
