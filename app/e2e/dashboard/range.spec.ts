import type { Page } from '@playwright/test'
import { expect, settle, snap, test, visit } from '../fixtures'
import { ready, type CardSpec } from './ready'

const DAY = 86400000
const shift = (iso: string, days: number) => new Date(Date.parse(iso) + days * DAY).toISOString().slice(0, 10)
const option = (page: Page, preset: string) => page.locator(`[data-testid="range-option"][data-preset="${preset}"]`)
const metricsWith = (page: Page, metrics: string[], param: string) =>
  Promise.all(metrics.map((metric) => page.waitForResponse((r) => r.url().includes(`/api/metrics/${metric}?`) && r.url().includes(param))))

test('presets and custom bounds', async ({ page }) => {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  const ranged = Object.entries<{ range: boolean; sections: { cards: CardSpec[] }[] }>(dashboards).find(([, spec]) => spec.range)
  test.skip(!ranged, 'no ranged page declared')
  const [name, spec] = ranged!
  const metrics = spec.sections.flatMap((s) => s.cards.flatMap((c) => (c.shape === 'table' || !c.metric ? [] : [c.metric])))
  await visit(page, `/${name}`)
  const bounds = page.getByTestId('range-bounds')
  const before = await bounds.textContent()
  const week = metricsWith(page, metrics, 'from=')
  await option(page, 'last7').click()
  await week
  await expect(option(page, 'last7')).toHaveAttribute('aria-pressed', 'true')
  await expect(bounds).not.toHaveText(before!)
  await settle(page)
  await option(page, 'custom').click()
  const [rangeFrom, rangeTo] = [page.getByTestId('range-from'), page.getByTestId('range-to')]
  await expect(rangeFrom).toHaveValue(/^\d{4}-\d{2}-\d{2}$/)
  await expect(rangeTo).toHaveValue(/^\d{4}-\d{2}-\d{2}$/)
  const from = shift(await rangeTo.inputValue(), -10)
  const custom = metricsWith(page, metrics, `from=${from}`)
  await rangeFrom.fill(from)
  await custom
  await expect(rangeTo).toHaveAttribute('min', from)
  await ready(page)
  await snap(page, 'dashboard-range-custom')
})
