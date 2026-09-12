import { expect, mockJson, settle, snap, test, visit } from '../fixtures'

test('dashboards unavailable', async ({ page }) => {
  await mockJson(page, '**/api/definitions/dashboards', { detail: 'dashboards unavailable' }, 500)
  await visit(page, '/')
  await expect(page.getByTestId('error-banner')).toHaveText('500 dashboards unavailable')
  await settle(page)
  await snap(page, 'dashboard-error')
})

test('metrics unavailable', async ({ page }) => {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  const plain = Object.entries<{ range: boolean; sections: { cards: { metric: string }[] }[] }>(dashboards).find(([, spec]) => !spec.range)
  test.skip(!plain, 'every page has a range')
  const [name, spec] = plain!
  await mockJson(page, '**/api/metrics/*', { detail: 'metric unavailable' }, 500)
  await visit(page, `/${name}`)
  for (const card of spec.sections.flatMap((s) => s.cards)) {
    await expect(page.getByTestId(`card-${card.metric}`).getByTestId('error-banner')).toHaveText('500 metric unavailable')
  }
  await settle(page)
  await snap(page, 'dashboard-error-cards')
})
