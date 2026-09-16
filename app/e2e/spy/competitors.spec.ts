import { expect, snap, test, visit } from '../fixtures'
import { ready } from '../dashboard/ready'

test('definition', async ({ page }) => {
  const spec = await (await page.request.get('/api/definitions/spy')).json()
  await visit(page, '/competitors')
  await expect(page.getByTestId('competitors-brand')).toContainText(spec.brand.name)
  await expect(page.getByTestId('competitors-table').locator('tbody tr')).toHaveCount(spec.competitors.length)
  await expect(page.getByTestId('competitors-queries').locator('li')).toHaveCount(spec.queries.length)
  await expect(page.getByTestId('competitors-sources').getByTestId('source-state').first()).toBeVisible({ timeout: 30_000 })
  await ready(page)
  await snap(page, 'spy-competitors')
})
