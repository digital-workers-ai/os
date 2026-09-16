import type { Page } from '@playwright/test'
import { expect, mockJson, snap, test, visit } from '../fixtures'
import { ready } from './ready'

const preset = (page: Page, name: string) => page.locator(`[data-testid="canvas-date-option"][data-preset="${name}"]`)

test('board', async ({ page }) => {
  await visit(page, '/')
  await ready(page)
  await expect(page.getByTestId('canvas-node')).toHaveCount(6)
  await expect(page.getByTestId('canvas-day')).toHaveCount(3)
  await expect(page.getByTestId('canvas-node-origin').filter({ hasText: 'marketer' })).toHaveCount(2)
  await expect(page.getByTestId('canvas-node-status')).toHaveText(['held'])

  await page.getByTestId('canvas-chip-image').click()
  await expect(page.getByTestId('canvas-node')).toHaveCount(2)
  await page.getByTestId('canvas-chip-image').click()
  await expect(page.getByTestId('canvas-node')).toHaveCount(6)

  await preset(page, 'today').click()
  await expect(preset(page, 'today')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('canvas-day')).toHaveCount(1)
  await expect(page.getByTestId('canvas-node')).toHaveCount(2)
  await ready(page)

  await preset(page, 'all').click()
  await expect(page.getByTestId('canvas-node')).toHaveCount(6)
  await ready(page)
  const first = page.getByTestId('canvas-node').first()
  await first.dblclick()
  await expect(page.getByTestId('canvas-preview')).toBeVisible()
  await expect(page.getByTestId('canvas-preview-image')).toBeVisible()
  await expect(page.getByTestId('canvas-preview-position')).toHaveText('1 / 6')
  await page.getByTestId('canvas-preview-close').click()
  await expect(page.getByTestId('canvas-preview')).toHaveCount(0)

  await first.click({ button: 'right' })
  await expect(page.getByTestId('canvas-menu')).toBeVisible()
  await expect(page.getByTestId('canvas-menu-open')).toHaveText('Open')
  await expect(page.getByTestId('canvas-menu-edit')).toHaveText('Edit')
  await page.locator('.react-flow__pane').click({ position: { x: 8, y: 8 } })
  await expect(page.getByTestId('canvas-menu')).toHaveCount(0)

  await ready(page)
  await snap(page, 'studio-canvas')
})

test('nothing made yet', async ({ page }) => {
  await mockJson(page, '**/api/studio/canvas*', { nodes: [] })
  await visit(page, '/')
  await ready(page)
  await expect(page.getByTestId('canvas-empty')).toContainText('Nothing has been made yet')
  await expect(page.getByTestId('canvas-empty-create')).toHaveAttribute('href', '/create')
  await expect(page.getByTestId('canvas-empty-calendar')).toHaveAttribute('href', '/calendar')
  await expect(page.getByTestId('canvas-board')).toHaveCount(0)
  await snap(page, 'studio-canvas-empty')
})
