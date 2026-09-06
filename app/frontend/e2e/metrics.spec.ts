import type { Page, Route } from '@playwright/test'
import { expect, header, mockJson, NOW, snap, test, visit } from './fixtures'

type MetricRow = Record<string, unknown>

const HOUR = 3600000
const DAY = 24 * HOUR
const at = (msAgo: number) => new Date(NOW.getTime() - msAgo).toISOString()

const series = (metric: string) => ({
  metric,
  runs: [
    {
      inferred: false,
      vocabulary_sha: null,
      produced_by: null,
      points: [
        { value: 120, entities: 5, recorded_at: at(3 * DAY) },
        { value: 140, entities: 6, recorded_at: at(2 * DAY) },
        { value: null, entities: 0, recorded_at: at(DAY) },
        { value: 160, entities: 7, recorded_at: at(HOUR) },
      ],
    },
  ],
  comparable: true,
  breaks: 0,
  inferred: false,
})

const metricOf = (route: Route) => decodeURIComponent(route.request().url().split('/').pop()!)
const mockSeries = (page: Page) => page.route('**/api/metrics/history/*', (r) => r.fulfill({ json: series(metricOf(r)) }))
const patchMetrics = (page: Page, patch: (metrics: Record<string, MetricRow>) => void) =>
  page.route('**/api/metrics', async (r) => {
    const json = await (await r.fetch()).json()
    patch(json.metrics)
    await r.fulfill({ json })
  })

const rows = (page: Page) => page.getByTestId('metrics-row')
const nameOf = async (row: ReturnType<typeof rows>) => (await row.getAttribute('data-name'))!
const labelOf = async (page: Page, row: ReturnType<typeof rows>) => {
  const { metrics } = await (await page.request.get('/api/metrics')).json()
  return metrics[await nameOf(row)].label as string
}
const title = (page: Page) => page.getByTestId('series-title')

test('nothing selected', async ({ page }) => {
  await visit(page, '/metrics')
  await expect(header(page.getByTestId('metrics-table'), 'Metric (14)')).toBeVisible()
  await expect(page.getByTestId('series').getByTestId('empty')).toHaveText('select a metric')
  await snap(page, 'metrics-default')
})

test('row selected', async ({ page }) => {
  await mockSeries(page)
  await visit(page, '/metrics')
  const row = rows(page).first()
  const label = await labelOf(page, row)
  await row.click()
  await expect(row).toHaveAttribute('aria-selected', 'true')
  await expect(title(page)).toHaveText(label)
  await expect(header(page.getByTestId('series-table'), 'Value')).toBeVisible()
  await snap(page, 'metrics-selected')
})

test('warning row', async ({ page }) => {
  await mockSeries(page)
  await visit(page, '/metrics')
  const warning = page.getByTestId('metrics-warning').first()
  test.skip((await warning.count()) === 0, 'no warning metric in fixture')
  await warning.click()
  const banner = page.getByTestId('series-note').or(page.getByTestId('series-mixed')).or(page.getByTestId('series-error'))
  await expect(banner.first()).toBeVisible()
  await snap(page, 'metrics-warning')
})

test('no-data note', async ({ page }) => {
  await patchMetrics(page, (metrics) => {
    const first = Object.keys(metrics)[0]
    metrics[first] = { ...metrics[first], note: 'no entities matched — no data', value: null }
  })
  await page.route('**/api/metrics/history/*', (r) =>
    r.fulfill({ json: { metric: metricOf(r), runs: [], comparable: true, breaks: 0, inferred: false } }),
  )
  await visit(page, '/metrics')
  await rows(page).first().click()
  await expect(page.getByTestId('series-note')).toHaveText('no entities matched — no data')
  await snap(page, 'metrics-no-data')
})

test('mixed currencies and error banners', async ({ page }) => {
  await patchMetrics(page, (metrics) => {
    const [first, second] = Object.keys(metrics)
    metrics[first].mixed_currencies = ['USD', 'EUR']
    metrics[second].error = 'boom'
  })
  await mockSeries(page)
  await visit(page, '/metrics')
  await rows(page).nth(0).click()
  await expect(page.getByTestId('series-mixed')).toHaveText('mixed currencies: USD, EUR')
  await snap(page, 'metrics-mixed-currencies')
  await rows(page).nth(1).click()
  await expect(page.getByTestId('series-error')).toHaveText('boom')
  await snap(page, 'metrics-error-metric')
})

test('series error', async ({ page }) => {
  await mockJson(page, '**/api/metrics/history/*', { detail: 'boom' }, 500)
  await visit(page, '/metrics')
  await rows(page).first().click()
  await expect(page.getByTestId('series').getByTestId('error-banner')).toHaveText('500 boom')
  await snap(page, 'metrics-series-error')
})

test('keeps the previous series while the next one loads', async ({ page }) => {
  let slow = ''
  await page.route('**/api/metrics/history/*', async (r) => {
    const metric = metricOf(r)
    if (metric === slow) await new Promise((resolve) => setTimeout(resolve, 1500))
    await r.fulfill({ json: series(metric) })
  })
  await visit(page, '/metrics')
  const [first, second] = [rows(page).nth(0), rows(page).nth(1)]
  const [labelA, labelB] = await Promise.all([labelOf(page, first), labelOf(page, second)])
  slow = await nameOf(second)
  await first.click()
  await expect(title(page)).toHaveText(labelA)
  await second.click()
  await expect(second).toHaveAttribute('aria-selected', 'true')
  await page.waitForTimeout(500)
  await expect(title(page)).toHaveText(labelA)
  await expect(title(page)).not.toHaveText(labelB)
  await expect(title(page)).toHaveText(labelB)
  await expect(title(page)).not.toHaveText(labelA)
})
