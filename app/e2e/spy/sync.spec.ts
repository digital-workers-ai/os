import type { Page } from '@playwright/test'
import { NOW, expect, mockJson, snap, test, visit } from '../fixtures'
import { ready } from './ready'

const SOURCES = ['meta_ad_library', 'google_ads_transparency', 'serp', 'ai_answers', 'competitor_pages', 'linkedin_posts']

const STALE = new Date(NOW.getTime() - 2 * 3_600_000).toISOString()

const SYNCED = { ok: 1, failed: 0, rows_written: 0, results: [] }

function gate() {
  let open!: () => void
  const wait = new Promise<void>((resolve) => (open = resolve))
  return { wait, open }
}

async function mockSync(page: Page, wait: Promise<void> = Promise.resolve()) {
  let body: unknown
  await page.route('**/api/sync', async (r) => {
    body = r.request().postDataJSON()
    await wait
    await r.fulfill({ json: SYNCED })
  })
  return () => body
}

test('last sync banner', async ({ page }) => {
  await visit(page, '/meta-ads')
  await ready(page)
  await expect(page.getByTestId('sync-banner')).toBeVisible()
  await expect(page.getByTestId('sync-banner-text')).toHaveText(/^Last sync: .+\.$/)
  await snap(page, 'spy-sync-banner')
})

test('sync now', async ({ page }) => {
  let synced = false
  const sync = gate()
  const rebuild = gate()
  await page.route('**/api/sources', (r) => {
    const last_success = synced ? NOW.toISOString() : STALE
    const sources = SOURCES.map((source) => ({ source, category: 'Competitors', last_attempt: last_success, last_success }))
    return r.fulfill({ json: { sources } })
  })
  const body = await mockSync(page, sync.wait)
  await page.route('**/api/rebuild', async (r) => {
    await rebuild.wait
    synced = true
    await r.fulfill({ json: { ok: true } })
  })
  await visit(page, '/meta-ads')
  await ready(page)
  await expect(page.getByTestId('sync-banner-text')).toHaveText('Last sync: 2 hours ago.')
  const button = page.getByTestId('sync-now')
  await button.click()
  await expect(button).toHaveText('Syncing…')
  await expect(button).toHaveAttribute('aria-busy', 'true')
  await expect(button).toBeDisabled()
  await expect.poll(body).toEqual({ sources: ['meta_ad_library'] })
  sync.open()
  await expect(button).toHaveText('Rebuilding…')
  rebuild.open()
  await expect(button).toHaveText('Sync now')
  await expect(button).toBeEnabled()
  await expect(page.getByTestId('sync-banner-text')).toHaveText(/just now\.$/)
})

test('sync now on linkedin', async ({ page }) => {
  const body = await mockSync(page)
  await mockJson(page, '**/api/rebuild', { ok: true })
  await visit(page, '/linkedin')
  await ready(page)
  await page.getByTestId('sync-now').click()
  await expect.poll(body).toEqual({ sources: ['linkedin_posts'] })
  await expect(page.getByTestId('sync-now')).toHaveText('Sync now')
})

test('rebuild already in progress', async ({ page }) => {
  await mockJson(page, '**/api/sync', SYNCED)
  await mockJson(page, '**/api/rebuild', { detail: 'a rebuild is already in progress' }, 409)
  await visit(page, '/meta-ads')
  await ready(page)
  await page.getByTestId('sync-now').click()
  await expect(page.getByTestId('sync-banner-text')).toHaveText('Sync failed: a rebuild is already in progress')
  await expect(page.getByTestId('sync-banner')).toHaveClass(/amber/)
  await expect(page.getByTestId('sync-now')).toBeEnabled()
  await page.unroute('**/api/rebuild')
  await mockJson(page, '**/api/rebuild', { ok: true })
  await page.getByTestId('sync-now').click()
  await expect(page.getByTestId('sync-banner-text')).toHaveText(/^Last sync: .+\.$/)
  await expect(page.getByTestId('sync-banner')).not.toHaveClass(/amber/)
})
