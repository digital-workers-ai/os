import type { Page } from '@playwright/test'
import { expect, NOW, settle, snap, test, visit } from './fixtures'

const ROUTES: [string, string][] = [
  ['/activity', 'Activity'],
  ['/metrics', 'Metrics'],
  ['/entities', 'Entities'],
  ['/ai', 'AI'],
  ['/definitions', 'Definitions'],
  ['/config', 'Config'],
]

const overlay = (page: Page) => page.locator('div.fixed.inset-0')

test.describe('intro', () => {
  test.use({ contextOptions: { reducedMotion: 'no-preference' } })

  test('plays through splash, header and page', async ({ page }) => {
    await page.clock.pauseAt(NOW)
    await page.goto('/')
    await settle(page)
    await expect(overlay(page)).toBeVisible()
    await page.clock.runFor(1200)
    await snap(page, 'intro-splash')
    await page.clock.runFor(2100)
    await expect(overlay(page)).toHaveCount(0)
    await expect(page.locator('main')).toHaveCSS('opacity', '0')
    await snap(page, 'intro-header')
    await page.clock.runFor(1700)
    await expect(page.locator('main')).toHaveCSS('opacity', '1')
    await snap(page, 'intro-done')
  })

  test('route change does not replay the intro', async ({ page }) => {
    await page.clock.pauseAt(NOW)
    await page.goto('/')
    await settle(page)
    await page.clock.runFor(5000)
    await expect(overlay(page)).toHaveCount(0)
    await page.getByRole('link', { name: 'Metrics' }).click()
    await expect(page.getByRole('heading', { name: 'Metrics' })).toBeVisible()
    await expect(overlay(page)).toHaveCount(0)
  })
})

test('nav marks the current route', async ({ page }) => {
  test.slow()
  for (const [path, label] of ROUTES) {
    await visit(page, path)
    const active = page.locator('nav a[aria-current="page"]')
    await expect(active).toHaveCount(1)
    await expect(active).toHaveText(label)
    await expect(active).toHaveClass(/bg-white/)
    await expect(page.locator('nav a.bg-white')).toHaveCount(1)
    await expect(page.locator('header')).toHaveScreenshot(`nav-${path.slice(1)}.png`)
  }
})

test('page never scrolls at lg', async ({ page }) => {
  test.slow()
  for (const [path] of ROUTES) {
    await visit(page, path)
    const [scrollHeight, innerHeight] = await page.evaluate(() => [document.documentElement.scrollHeight, window.innerHeight])
    expect(scrollHeight, path).toBeLessThanOrEqual(innerHeight)
  }
})
