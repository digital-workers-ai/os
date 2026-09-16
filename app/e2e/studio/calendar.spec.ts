import type { Page } from '@playwright/test'
import { expect, mockJson, NOW, snap, test, visit } from '../fixtures'
import { ready } from './ready'

interface Slot {
  date: string
  name: string
  state: string
}

const MONTH = NOW.toISOString().slice(0, 7)

const AGENT_RUN = {
  seq: 91,
  agent: 'marketer',
  trigger: 'manual',
  read_detail: '9 slots, 5 empty',
  made: 0,
  duration_ms: 1200,
  ok: true,
  error: null,
  created_at: NOW.toISOString(),
}

const chip = (page: Page, slot: Slot) => page.locator(`[data-testid="calendar-slot"][data-date="${slot.date}"][data-name="${slot.name}"]`).first()

const calendarLoaded = (page: Page) => page.waitForResponse((r) => r.url().includes('/api/studio/calendar?'))

test('month, week and list', async ({ page }) => {
  const { slots } = (await (await page.request.get(`/api/studio/calendar?from=${MONTH}-01&to=${MONTH}-28`)).json()) as { slots: Slot[] }
  const names = [...new Set(slots.map((slot) => slot.name))]
  const skipped = slots.find((slot) => slot.state === 'skipped')!
  const empty = slots.find((slot) => slot.state === 'empty')!
  expect(names).toHaveLength(4)
  expect(skipped).toBeDefined()

  await visit(page, '/calendar')
  await ready(page)
  await expect(page.getByTestId('calendar-month')).toBeVisible()
  await expect(page.getByTestId('calendar-label')).toContainText('2026')
  for (const name of names) await expect(page.locator(`[data-testid="calendar-slot"][data-name="${name}"]`).first()).toBeVisible()
  await expect(chip(page, skipped)).toContainText('×')
  await expect(page.getByTestId('calendar-legend')).toContainText('× skipped')

  await chip(page, empty).click()
  const dialog = page.getByTestId('slot-dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText(empty.name)
  await expect(page.getByTestId('slot-run')).toHaveText('Run now')
  await expect(page.getByTestId('slot-skip')).toHaveText('Skip')
  await page.getByTestId('slot-close').click()
  await expect(dialog).toHaveCount(0)

  const week = calendarLoaded(page)
  await page.getByTestId('calendar-mode-week').click()
  await week
  await ready(page)
  await expect(page.getByTestId('calendar-week')).toBeVisible()

  const list = calendarLoaded(page)
  await page.getByTestId('calendar-mode-list').click()
  await list
  await ready(page)
  await expect(page.getByTestId('calendar-list')).toBeVisible()

  const month = calendarLoaded(page)
  await page.getByTestId('calendar-mode-month').click()
  await month
  await ready(page)
  await expect(page.getByTestId('calendar-month')).toBeVisible()
  await snap(page, 'studio-calendar')
})

test('fill the next fortnight', async ({ page }) => {
  await mockJson(page, '**/api/studio/calendar/fill', { agent_run: AGENT_RUN })
  await visit(page, '/calendar')
  await ready(page)
  const filled = page.waitForRequest((r) => r.url().includes('/api/studio/calendar/fill') && r.method() === 'POST')
  await page.getByTestId('calendar-fill').click()
  await filled
  await expect(page.getByTestId('calendar-fill-error')).toHaveCount(0)
  await expect(page.getByTestId('calendar-fill')).toHaveText('Fill next 14 days')
  await ready(page)
  await snap(page, 'studio-calendar-fill')
})
