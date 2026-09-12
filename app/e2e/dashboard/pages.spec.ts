import { expect, snap, test, visit } from '../fixtures'
import { ready } from './ready'

interface PageSpec {
  range: boolean
  sections: { cards: { metric: string }[] }[]
}

test('each page', async ({ page }) => {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  for (const [name, spec] of Object.entries<PageSpec>(dashboards)) {
    await visit(page, `/${name}`)
    await expect(page.getByTestId(`nav-${name}`)).toHaveAttribute('aria-current', 'page')
    for (const card of spec.sections.flatMap((s) => s.cards)) await expect(page.getByTestId(`card-${card.metric}`)).toBeVisible()
    await expect(page.getByTestId('range-picker')).toHaveCount(spec.range ? 1 : 0)
    await ready(page)
    await snap(page, `dashboard-${name}`)
  }
})
