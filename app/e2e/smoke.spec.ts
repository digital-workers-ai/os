import { expect, snap, test, visit } from './fixtures'

test('home', async ({ page }) => {
  await visit(page, '/')
  await expect(page.getByRole('heading', { name: 'Insights' })).toBeVisible()
  await snap(page, 'home')
})
