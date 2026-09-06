import { test as base, expect, type Locator, type Page } from '@playwright/test'

export const NOW = new Date('2026-09-04T12:00:00Z')

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.clock.setFixedTime(NOW)
    await use(page)
  },
})

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export function header(scope: Locator | Page, label: string | RegExp) {
  return scope.locator('th').filter({ hasText: typeof label === 'string' ? new RegExp(`^${escape(label)}$`) : label })
}

export async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForLoadState('networkidle')
  await expect(page.getByTestId('loading')).toHaveCount(0)
}

export async function visit(page: Page, path: string) {
  await page.goto(path)
  await settle(page)
}

export async function snap(
  page: Page,
  name: string,
  options?: Parameters<ReturnType<typeof expect<Page>>['toHaveScreenshot']>[1],
) {
  await expect(page).toHaveScreenshot(`${name}.png`, options)
}

export async function openFilter(page: Page, testId: string) {
  await page.getByTestId(testId).click()
  await page.locator('[role=listbox]').waitFor()
}

export async function pickOption(page: Page, testId: string, value: string) {
  await openFilter(page, testId)
  await page.locator(`[data-testid="${testId}-option"][data-value="${value}"]`).click()
}

export async function mockJson(page: Page, url: string, body: unknown, status = 200) {
  await page.route(url, r => r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) }))
}

export { expect }
