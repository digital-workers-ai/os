import { expect, snap, test, visit } from '../fixtures'
import { ready } from './ready'

interface TodayResponse {
  today: string
  last_run: { agent: string; read_detail: string; created_at: string } | null
  week: { date: string; name: string; state: string }[]
  built_today: { seq: number; name: string }[]
}

test('the day so far', async ({ page }) => {
  const data: TodayResponse = await (await page.request.get('/api/studio/today')).json()
  expect(data.last_run).not.toBeNull()
  await visit(page, '/today')
  await ready(page)

  const header = page.getByTestId('today-header')
  await expect(header).toContainText(data.today)
  await expect(header).toContainText(`${data.last_run!.agent} ran ${data.last_run!.created_at.slice(11, 16)}`)
  await expect(header).toContainText(`read ${data.last_run!.read_detail}`)

  await expect(page.getByTestId('today-slot')).toHaveCount(data.week.length)
  await expect(page.getByTestId('today-week')).toContainText('○')
  for (const slot of data.week) {
    await expect(page.locator(`[data-testid="today-slot"][data-state="${slot.state}"]`).first()).toBeVisible()
  }

  await expect(page.getByTestId('today-built')).toBeVisible()
  await expect(page.getByTestId('today-asset')).toHaveCount(data.built_today.length)
  for (const asset of data.built_today) await expect(page.getByTestId('today-built')).toContainText(asset.name)

  await ready(page)
  await snap(page, 'studio-today')
})
