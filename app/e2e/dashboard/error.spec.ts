import { expect, mockJson, settle, snap, test, visit } from '../fixtures'
import { cardId, type CardSpec } from './ready'

test('dashboards unavailable', async ({ page }) => {
  await mockJson(page, '**/api/definitions/dashboards', { detail: 'dashboards unavailable' }, 500)
  await visit(page, '/')
  await expect(page.getByTestId('error-banner')).toHaveText('500 dashboards unavailable')
  await settle(page)
  await snap(page, 'dashboard-error')
})

test('metrics unavailable', async ({ page }) => {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  const plain = Object.entries<{ range: boolean; sections: { cards: CardSpec[] }[] }>(dashboards).find(([, spec]) => !spec.range && spec.sections.some((s) => s.cards.length > 0))
  test.skip(!plain, 'no unranged page with cards')
  const [name, spec] = plain!
  await mockJson(page, '**/api/metrics/*', { detail: 'metric unavailable' }, 500)
  await mockJson(page, '**/api/entities/top*', { detail: 'records unavailable' }, 500)
  await visit(page, `/${name}`)
  const cards = spec.sections.flatMap((s) => s.cards)
  expect(cards.length).toBeGreaterThan(0)
  for (const card of cards) {
    const detail = card.shape === 'table' ? 'records unavailable' : 'metric unavailable'
    await expect(page.getByTestId(cardId(card)).getByTestId('error-banner')).toHaveText(`500 ${detail}`)
  }
  await settle(page)
  await snap(page, 'dashboard-error-cards')
})
