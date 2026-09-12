import { expect, settle, snap, test, visit } from '../fixtures'

test('default', async ({ page }) => {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  const [name, spec] = Object.entries<{ sections: { cards: { metric: string }[] }[] }>(dashboards)[0]
  await visit(page, '/')
  await expect(page).toHaveURL(new RegExp(`/${name}$`))
  for (const tab of Object.keys(dashboards)) await expect(page.getByTestId(`nav-${tab}`)).toBeVisible()
  await expect(page.locator('[data-testid="range-option"][data-preset="last30"]')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('range-bounds')).toBeVisible()
  for (const card of spec.sections.flatMap((s) => s.cards)) await expect(page.getByTestId(`card-${card.metric}`)).toBeVisible()
  await settle(page)
  await snap(page, 'dashboard-overview')
})
