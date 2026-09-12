import { expect, snap, test, visit } from '../fixtures'
import { ready } from './ready'

test('drawer', async ({ page }) => {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  const card = Object.values<{ sections: { cards: { metric: string; label: string }[] }[] }>(dashboards)[0].sections[0].cards[0]
  await visit(page, '/')
  await page.getByTestId(`definition-${card.metric}`).click()
  const drawer = page.getByTestId('definition')
  await expect(drawer).toBeVisible()
  await expect(drawer.getByRole('heading', { name: card.label, exact: true })).toBeVisible()
  await expect(drawer.getByRole('heading', { name: 'Sources', exact: true })).toBeVisible()
  await expect(drawer.getByRole('heading', { name: 'Receipts', exact: true })).toBeVisible()
  await expect(drawer.getByTestId('open-in-console')).toHaveAttribute('href', new RegExp(`/definitions/metrics\\?metric=${card.metric}$`))
  await ready(page)
  await snap(page, 'dashboard-definition')
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
})
