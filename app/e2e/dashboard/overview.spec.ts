import { expect, snap, test, visit } from '../fixtures'
import { ready } from './ready'

interface PageSpec {
  parent: string | null
  sections: { cards: { metric: string }[] }[]
}

test('default', async ({ page }) => {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  const pages = Object.entries<PageSpec>(dashboards)
  const [name, spec] = pages[0]
  await visit(page, '/')
  await expect(page).toHaveURL(new RegExp(`/${name}$`))
  for (const [tab, { parent }] of pages) if (parent === null) await expect(page.getByTestId(`nav-${tab}`)).toBeVisible()
  await expect(page.locator('[data-testid="range-option"][data-preset="last30"]')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('range-bounds')).toBeVisible()
  for (const card of spec.sections.flatMap((s) => s.cards)) await expect(page.getByTestId(`card-${card.metric}`)).toBeVisible()
  await ready(page)
  await snap(page, 'dashboard-overview')
})
