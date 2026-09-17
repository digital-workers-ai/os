import type { Page } from '@playwright/test'
import { expect, mockJson, NOW, snap, test, visit } from '../fixtures'
import { ready } from './ready'

interface AssetRow {
  seq: number
  version: number
}

const RUNNING = {
  seq: 901,
  skill: 'dw-image',
  skill_sha: 'a3f9c0',
  caller: 'chat',
  asset_seq: 0,
  version: 3,
  stage: 'painting',
  status: 'running',
  error: null,
  model: 'claude-opus-5',
  tokens_in: 0,
  tokens_out: 0,
  duration_ms: 0,
  started_at: NOW.toISOString(),
  finished_at: null,
}

const FINISHED = {
  ...RUNNING,
  stage: null,
  status: 'ok',
  tokens_in: 9100,
  tokens_out: 1300,
  duration_ms: 41000,
  finished_at: NOW.toISOString(),
  tool_calls: [
    { id: 1, tool: 'image_paint', ok: true, duration_ms: 1400, detail: 'painted one picture, no words in it' },
    { id: 2, tool: 'image_render', ok: true, duration_ms: 900, detail: 'rendered the card over the picture' },
  ],
  files: [],
}

const version = (page: Page, number: number) => page.locator(`[data-testid="asset-version"][data-version="${number}"]`)

async function remade(page: Page): Promise<number> {
  const { assets } = (await (await page.request.get('/api/assets?kind=image')).json()) as { assets: AssetRow[] }
  const twice = assets.find((asset) => asset.version === 2)!
  expect(twice).toBeDefined()
  return twice.seq
}

test('two versions', async ({ page }) => {
  const seq = await remade(page)
  await visit(page, `/assets/${seq}`)
  await ready(page)
  await expect(page.getByTestId('asset-name')).toHaveText('100% line and branch coverage')
  await expect(page.getByTestId('asset-meta')).toHaveText('image · stat-card · 1:1')
  await expect(page.getByTestId('origin-pill')).toHaveText('chat')

  await expect(page.getByTestId('asset-preview')).toHaveAttribute('data-version', '2')
  await expect(page.getByTestId('asset-preview-image')).toHaveAttribute('src', new RegExp(`/api/assets/${seq}/versions/2/files/image.png$`))
  await expect(page.getByTestId('asset-version')).toHaveCount(2)
  await expect(version(page, 2)).toContainText('shorter label')

  await version(page, 1).click()
  await expect(page.getByTestId('asset-preview')).toHaveAttribute('data-version', '1')
  await expect(page.getByTestId('asset-preview-image')).toHaveAttribute('src', new RegExp(`/api/assets/${seq}/versions/1/files/image.png$`))

  await expect(page.getByTestId('asset-lineage')).toContainText('dw-image')
  await expect(page.getByTestId('asset-read')).toContainText('proof.md')
  await expect(page.getByTestId('asset-claim')).toHaveCount(3)
  await expect(page.getByTestId('asset-claim').first()).toContainText('✓')
  await expect(page.getByTestId('edit-input')).toBeVisible()
  await expect(page.getByTestId('resize-4-5')).toHaveText('4:5')
  await expect(page.getByTestId('resize-9-16')).toHaveText('9:16')
  await expect(page.getByTestId('resize-16-9')).toHaveText('16:9')

  await ready(page)
  await snap(page, 'studio-asset')
})

test('an edit makes a new version', async ({ page }) => {
  const seq = await remade(page)
  await mockJson(page, `**/api/assets/${seq}/edit`, { skill_run: { ...RUNNING, asset_seq: seq }, version: 3 })
  await mockJson(page, '**/api/skill-runs/*', { ...FINISHED, asset_seq: seq })
  await visit(page, `/assets/${seq}`)
  await ready(page)

  const edited = page.waitForRequest((r) => r.url().endsWith(`/api/assets/${seq}/edit`) && r.method() === 'POST')
  await page.getByTestId('edit-input').fill('Shorter label, and keep the number')
  await page.getByTestId('edit-send').click()
  await edited
  await expect(page.getByTestId('edit-run')).toBeVisible()
  await expect(page.getByTestId('run-progress')).toHaveAttribute('data-status', 'ok')
  await expect(page.getByTestId('run-tools')).toContainText('image_paint ×1')
  await expect(page.getByTestId('run-tools')).toContainText('image_render ×1')
  await expect(page.getByTestId('edit-input')).toHaveValue('')

  await ready(page)
  await snap(page, 'studio-asset-edit')
})
