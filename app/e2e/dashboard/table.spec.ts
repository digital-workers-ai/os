import { expect, test, visit } from '../fixtures'
import { cardId, ready } from './ready'

interface Card {
  shape: string
}

interface TableCard extends Card {
  shape: 'table'
  entity: string
  rank: string
  columns: { attr: string; type: string }[]
  limit: number
}

interface PageSpec {
  sections: { cards: Card[] }[]
}

const isTable = (card: Card): card is TableCard => card.shape === 'table'

test('table card', async ({ page }) => {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  const found = Object.entries<PageSpec>(dashboards)
    .flatMap(([name, spec]) => spec.sections.flatMap((s) => s.cards.filter(isTable).map((card) => ({ name, card }))))
    .at(0)
  test.skip(!found, 'no page declares a table card')
  const { name, card } = found!
  await visit(page, `/${name}`)
  const table = page.getByTestId(cardId(card))
  await expect(table).toBeVisible()
  await expect(table).toHaveAttribute('data-state', 'ready', { timeout: 20_000 })
  await expect(table.locator('thead th')).toHaveText(card.columns.map((c) => c.attr.replace(/_/g, ' ')))
  const rows = table.locator('tbody tr')
  expect(await rows.count()).toBeLessThanOrEqual(card.limit)
  await expect(rows.first().locator(`td[data-attr="${card.rank}"]`)).toHaveText(/\S/)
  await ready(page)
  await expect(table).toHaveScreenshot('dashboard-table.png')
})
