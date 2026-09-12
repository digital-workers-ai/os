import { expect, NOW, settle, snap, test, visit } from './fixtures'
import { PATH } from '../console/src/paths'

const ROUTES: [string, string][] = [
  [PATH.activity, 'Activity'],
  [PATH.metrics, 'Metrics'],
  [PATH.entities, 'Entities'],
  [PATH.ai, 'AI'],
  [PATH.definitions, 'Definitions'],
  [PATH.config, 'Config'],
  [PATH.search, 'Search'],
]

const NAV = ['home', 'activity', 'metrics', 'entities', 'ai', 'definitions', 'config', 'search']

test.describe('intro', () => {
  test.use({ contextOptions: { reducedMotion: 'no-preference' } })

  test('plays through splash, header and page', async ({ page }) => {
    await page.clock.pauseAt(NOW)
    await page.goto(PATH.home)
    await settle(page)
    await expect(page.getByTestId('intro')).toBeVisible()
    await page.clock.runFor(1200)
    await snap(page, 'intro-splash')
    await page.clock.runFor(2100)
    await expect(page.getByTestId('intro')).toHaveCount(0)
    await expect(page.getByTestId('page-main')).toHaveCSS('opacity', '0')
    await snap(page, 'intro-header')
    await page.clock.runFor(1700)
    await expect(page.getByTestId('page-main')).toHaveCSS('opacity', '1')
    await snap(page, 'intro-done')
  })

  test('route change does not replay the intro', async ({ page }) => {
    await page.clock.pauseAt(NOW)
    await page.goto(PATH.home)
    await settle(page)
    await page.clock.runFor(5000)
    await expect(page.getByTestId('intro')).toHaveCount(0)
    await page.getByTestId('nav-metrics').click()
    await expect(page.getByTestId('page-heading')).toHaveText('Metrics')
    await expect(page.getByTestId('intro')).toHaveCount(0)
  })
})

test('nav marks the current route', async ({ page }) => {
  test.slow()
  for (const [path, label] of ROUTES) {
    await visit(page, path)
    const id = `nav-${path.slice(1)}`
    const active = page.getByTestId(id)
    await expect(active).toHaveAttribute('aria-current', 'page')
    await expect(active).toHaveText(label)
    await expect(active).toHaveClass(/bg-white/)
    for (const other of NAV.filter((n) => n !== path.slice(1))) await expect(page.getByTestId(`nav-${other}`)).not.toHaveClass(/bg-white/)
    await expect(page.getByTestId('top-nav')).toHaveScreenshot(`nav-${path.slice(1)}.png`)
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
