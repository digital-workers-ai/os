import { expect, snap, test, visit } from '../fixtures'
import { ready } from '../dashboard/ready'

test('matrix', async ({ page }) => {
  const { queries } = await (await page.request.get('/api/definitions/spy')).json()
  await visit(page, '/visibility')
  await expect(page.getByTestId('sub-nav').locator('a')).toHaveCount(7)
  await expect(page.getByTestId('subnav-all')).toHaveAttribute('aria-current', 'page')
  const rows = page.getByTestId('visibility-row')
  await expect(rows).toHaveCount(queries.length, { timeout: 30_000 })
  await rows.first().click()
  await expect(rows.first().getByRole('button')).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByTestId('visibility-expanded')).toBeVisible()
  await ready(page)
  await snap(page, 'spy-visibility-expanded')
  await visit(page, '/visibility/chatgpt')
  await expect(page.getByTestId('subnav-chatgpt')).toHaveAttribute('aria-current', 'page')
  await expect(rows).toHaveCount(queries.length, { timeout: 30_000 })
  await ready(page)
  await snap(page, 'spy-visibility-chatgpt')
})
