import { test as base, expect, type Page } from '@playwright/test'

export const NOW = new Date('2026-09-04T12:00:00Z')

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.clock.setFixedTime(NOW)
    await use(page)
  },
})

export async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForLoadState('networkidle')
  await expect(page.getByText('loading…')).toHaveCount(0)
}

export async function visit(page: Page, path: string) {
  await page.goto(path)
  await settle(page)
}

export async function snap(page: Page, name: string) {
  await expect(page).toHaveScreenshot(`${name}.png`)
}

export async function openSelect(page: Page, current: string) {
  await page.locator('[role=combobox]', { hasText: current }).click()
  await page.locator('[role=listbox]').waitFor()
}

export async function mockJson(page: Page, url: string, body: unknown, status = 200) {
  await page.route(url, r => r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) }))
}

export { expect }
