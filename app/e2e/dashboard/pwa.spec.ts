import { expect, test, visit } from '../fixtures'

test('manifest linked', async ({ page }) => {
  await visit(page, '/')
  await expect(page.locator('link[rel=manifest]')).toHaveAttribute('href', '/manifest.json')
  await expect(page.locator('link[rel=apple-touch-icon]')).toHaveCount(1)
})

test('manifest served', async ({ page }) => {
  const res = await page.request.get('/manifest.json')
  expect(res.status()).toBe(200)
  expect(res.headers()['content-type']).toContain('json')
  const manifest = await res.json()
  expect(manifest.display).toBe('standalone')
  expect(manifest.start_url).toBe('/')
  expect(manifest.icons).toHaveLength(4)
  for (const icon of manifest.icons as { src: string }[]) {
    const png = await page.request.get(icon.src)
    expect(png.status(), icon.src).toBe(200)
    expect(png.headers()['content-type'], icon.src).toMatch(/^image\/png/)
  }
})

test('worker served', async ({ page }) => {
  const res = await page.request.get('/sw.js')
  expect(res.status()).toBe(200)
  const text = await res.text()
  expect(text).toContain("addEventListener('fetch'")
  expect(text).toContain("'/api'")
})

test('apple touch icon served', async ({ page }) => {
  const res = await page.request.get('/apple-touch-icon.png')
  expect(res.status()).toBe(200)
  expect(res.headers()['content-type']).toMatch(/^image\/png/)
})
