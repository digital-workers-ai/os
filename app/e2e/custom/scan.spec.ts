import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { RECORD_PAGE, ready } from './ready'
import { lookedUp } from './seeded'

async function typedCode(page: Page, app: string, code: string) {
  await visit(page, `/apps/${app}/new`)
  await ready(page)
  const typed = page.getByTestId('scan-code')
  await typed.fill(code)
  await typed.press('Enter')
  await expect(page.getByTestId('field-asset')).toHaveValue(code)
}

test('the camera starts only on a tap', async ({ page }) => {
  await visit(page, '/apps/equipment_checkout/new')
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Equipment check-out')
  await expect(page.getByTestId('scan-start')).toBeVisible()
  await expect(page.getByTestId('scan-code')).toBeEditable()
  await expect(page.locator('video')).toHaveCount(0)
  await page.getByTestId('scan-start').click()
  await expect(page.locator('video')).toBeVisible()
})

test('a typed code finds the seeded asset', async ({ page }) => {
  const { matches } = await lookedUp(page, 'equipment_checkout', 'asset', 'LAP-014')
  expect(matches.map((match) => match.value)).toEqual(['LAP-014'])
  await typedCode(page, 'equipment_checkout', 'LAP-014')
  await expect(page.getByTestId('page-main').getByText(matches[0].label, { exact: true }).first()).toBeVisible()
  await expect(page.getByText('New asset')).toHaveCount(0)
  await ready(page)
  await snap(page, 'custom-scan-found')
})

test('an unknown code is kept as a new asset', async ({ page }) => {
  const { matches } = await lookedUp(page, 'equipment_checkout', 'asset', 'CAM-777')
  expect(matches).toEqual([])
  await typedCode(page, 'equipment_checkout', 'CAM-777')
  await expect(page.getByTestId('page-main').getByText('New asset')).toBeVisible()
  await page.getByTestId('field-action').selectOption('check_out')
  await page.getByTestId('field-location').fill('Studio B')
  await ready(page)
  await snap(page, 'custom-scan-new')

  await page.getByTestId('save').click()
  await expect(page).toHaveURL(RECORD_PAGE)
  await ready(page)
  await expect(page.getByTestId('field-asset')).toHaveValue('CAM-777')
  await expect(page.getByTestId('field-action')).toHaveValue('check_out')
})

test('a scanned maintenance tag shows its service history', async ({ page }) => {
  const { history } = await lookedUp(page, 'maintenance_tags', 'asset', 'PRESS-02')
  expect(history.length).toBeGreaterThan(0)
  await typedCode(page, 'maintenance_tags', 'PRESS-02')
  await expect(page.getByTestId('page-main').getByText('Replaced hydraulic seal').first()).toBeVisible()
  await ready(page)
  await snap(page, 'custom-scan-history')
})
