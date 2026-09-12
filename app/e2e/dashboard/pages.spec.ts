import { expect, snap, test, visit } from '../fixtures'
import { cardId, pagePath, ready, type CardSpec } from './ready'

interface PageSpec {
  parent: string | null
  range: boolean
  sections: { cards: CardSpec[] }[]
}

test('each page', async ({ page }) => {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  const pages = Object.entries<PageSpec>(dashboards)
  for (const [name, spec] of pages) {
    await visit(page, pagePath(name, spec))
    await expect(page.getByTestId(`nav-${spec.parent ?? name}`)).toHaveAttribute('aria-current', 'page')
    if (spec.parent) await expect(page.getByTestId(`subnav-${name}`)).toHaveAttribute('aria-current', 'page')
    else if (pages.some(([, other]) => other.parent === name)) await expect(page.getByTestId('subnav-all')).toHaveAttribute('aria-current', 'page')
    else await expect(page.getByTestId('sub-nav')).toHaveCount(0)
    for (const card of spec.sections.flatMap((s) => s.cards)) await expect(page.getByTestId(cardId(card))).toBeVisible()
    await expect(page.getByTestId('range-picker')).toHaveCount(spec.range ? 1 : 0)
    await ready(page)
    await snap(page, `dashboard-${name}`)
  }
})
