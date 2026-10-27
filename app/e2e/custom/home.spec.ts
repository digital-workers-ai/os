import type { Page } from '@playwright/test'
import { expect, mockJson, snap, test, visit } from '../fixtures'
import { ready } from './ready'
import { APPS } from './seeded'

interface AppRow {
  name: string
  title: string
}

const cards = (page: Page) => page.locator('[data-testid^="app-card-"]')

test('home lists the 21 apps under an Apps header, with a New app link', async ({ page }) => {
  const response = await page.request.get('/api/custom/apps')
  await expect(response).toBeOK()
  const apps = (await response.json()) as AppRow[]
  expect(apps.map((app) => app.name).sort()).toEqual(Object.keys(APPS).sort())
  await visit(page, '/')
  await ready(page)
  await expect(page).toHaveTitle(/^(Digital Workers )?Apps$/)
  await expect(page.getByRole('banner').getByText('Apps', { exact: true })).toBeVisible()
  await expect(page.getByRole('banner')).not.toContainText('DW Apps')
  await expect(cards(page)).toHaveCount(21)
  for (const [name, { title }] of Object.entries(APPS)) await expect(page.getByTestId(`app-card-${name}`)).toContainText(title)
  await expect(page.getByRole('link', { name: 'New app' })).toHaveAttribute('href', '/new-app')
  await ready(page)
  await snap(page, 'custom-home')
})

test('a card opens a new record', async ({ page }) => {
  await visit(page, '/')
  await ready(page)
  await page.getByTestId('app-card-receipts').click()
  await expect(page).toHaveURL(/\/apps\/receipts\/new$/)
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Receipts')
})

test('no apps shows the empty state and still offers New app', async ({ page }) => {
  await mockJson(page, '**/api/custom/apps', [])
  await visit(page, '/')
  await ready(page)
  await expect(cards(page)).toHaveCount(0)
  await expect(page.getByTestId('page-main')).toContainText('No apps yet')
  await expect(page.getByRole('link', { name: 'New app' })).toHaveAttribute('href', '/new-app')
  await snap(page, 'custom-home-empty')
})

test('the phone name is DW Apps', async ({ page }) => {
  const manifest = await (await page.request.get('/manifest.json')).json()
  expect(manifest.short_name).toBe('DW Apps')
  await visit(page, '/')
  await expect(page.locator('meta[name="apple-mobile-web-app-title"]')).toHaveAttribute('content', 'DW Apps')
})

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
