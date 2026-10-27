import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { APPS } from '../custom/seeded'
import { builder, mockBuilder, opened, ready, say, sent } from './ready'

const appRow = (page: Page, name: string) => page.locator(`[data-testid="app-row"][data-name="${name}"]`)

const field = (page: Page, name: string) => page.locator(`[data-testid="app-field"][data-name="${name}"]`)

async function shipped(page: Page, app: string): Promise<string> {
  const response = await page.request.get(`/api/builder/apps/${app}/yaml`)
  await expect(response).toBeOK()
  return ((await response.json()) as { yaml: string }).yaml
}

test('the apps list shows the 21 apps and opens one', async ({ page }) => {
  await visit(page, '/')
  await ready(page)
  await expect(page).toHaveTitle('App Builder')
  await expect(page.getByTestId('brand')).toContainText('App Builder')
  await expect(page.getByTestId('app-row')).toHaveCount(21)
  for (const [name, app] of Object.entries(APPS)) {
    const row = appRow(page, name)
    for (const text of [name, app.title, ...app.input, app.lands_as, ...app.roles]) await expect(row).toContainText(text)
    for (const file of ['script.py', 'screen.tsx']) {
      if (file === app.code) await expect(row).toContainText(file)
      else await expect(row).not.toContainText(file)
    }
  }
  await expect(page.getByRole('link', { name: 'New app' })).toHaveAttribute('href', '/new')
  await snap(page, 'builder-apps')

  await appRow(page, 'receipts').getByRole('link', { name: 'Receipts' }).click()
  await expect(page).toHaveURL(/\/apps\/receipts$/)
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Receipts')
})

test('an app page shows its fields and its app.yaml', async ({ page }) => {
  const yaml = await shipped(page, 'receipts')
  await visit(page, '/apps/receipts')
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Receipts')
  for (const text of ['photo', 'expense', 'staff', 'finance']) await expect(page.getByTestId('app-facts')).toContainText(text)
  const types: [string, string][] = [
    ['vendor', 'text'],
    ['date', 'date'],
    ['total', 'money'],
    ['tax', 'money'],
    ['category', 'one_of'],
    ['items', 'list'],
    ['items.description', 'text'],
    ['items.amount', 'money'],
  ]
  for (const [name, type] of types) await expect(field(page, name)).toContainText(type)
  await expect(page.getByTestId('app-field')).toHaveCount(types.length)
  for (const text of ['fuel', 'Gas, diesel or charging for a vehicle', 'other', 'Anything none of the above fits'])
    await expect(field(page, 'category')).toContainText(text)
  await expect(field(page, 'items')).toContainText('expense_item')
  expect(await page.getByTestId('app-yaml').textContent()).toBe(yaml)
  await expect(page.getByTestId('app-view').getByRole('textbox')).toHaveCount(0)
  await ready(page)
  await snap(page, 'builder-app')
})

test('lookups and template parts read plainly', async ({ page }) => {
  await visit(page, '/apps/maintenance_tags')
  await ready(page)
  for (const text of ['lookup', 'asset', 'code', 'from a scan', 'with its history']) await expect(field(page, 'asset')).toContainText(text)
  for (const text of ['out_of_service', 'Must not be used']) await expect(field(page, 'status')).toContainText(text)

  await visit(page, '/apps/perio_charting')
  await ready(page)
  for (const text of ['person', 'name']) await expect(field(page, 'patient')).toContainText(text)
  const grid = page.getByTestId('app-template')
  await expect(grid).toHaveAttribute('data-kind', 'grid')
  for (const text of ['tooth', '32', 'perio_tooth', 'site', 'DB', 'ML', 'perio_site']) await expect(grid).toContainText(text)
  for (const name of ['rows.status', 'rows.mobility', 'cells.depth', 'cells.bleeding']) await expect(field(page, name)).toBeVisible()
  await expect(field(page, 'cells.depth')).toContainText('mm')
  await ready(page)
  await snap(page, 'builder-app-grid')

  await visit(page, '/apps/vehicle_pre_trip')
  await ready(page)
  const checklist = page.getByTestId('app-template')
  await expect(checklist).toHaveAttribute('data-kind', 'checklist')
  for (const text of ['vehicle', 'service_brakes', 'tires', 'emergency_equipment', 'vehicle_check_item']) await expect(checklist).toContainText(text)
  for (const text of ['one_of', 'pass', 'fail']) await expect(field(page, 'items.result')).toContainText(text)
})

test('Change this app starts a thread for that app', async ({ page }) => {
  const yaml = await shipped(page, 'receipts')
  const CHANGE = 'Add the last four digits of the card that paid'
  const CHANGED = `${yaml.trimEnd()}\n  card_last_four: { type: text }`
  await mockBuilder(page, { replies: [builder('Added the card.', { draft: CHANGED })] })
  await visit(page, '/apps/receipts')
  await ready(page)

  const started = sent(page, 'threads')
  await page.getByRole('button', { name: 'Change this app' }).click()
  expect((await started).postDataJSON()).toEqual({ app: 'receipts' })
  await opened(page)
  await expect(page.getByTestId('thread-app')).toHaveAttribute('href', '/apps/receipts')
  await expect(page.getByTestId('thread-app')).toHaveText('Changing Receipts')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Change Receipts')
  await expect(page.getByTestId('turns-empty')).toContainText('Say what should change in Receipts.')
  await expect(page.getByTestId('turns-empty')).toBeVisible()
  await expect(page.getByTestId('builder-draft')).toHaveCount(0)

  expect(await say(page, CHANGE)).toEqual({ text: CHANGE })
  await expect(page.getByTestId('turn')).toHaveCount(2)
  await expect(page.getByTestId('builder-draft')).toContainText('card_last_four: { type: text }')
  await expect(page.getByTestId('thread')).toContainText('Receipts')
  await ready(page)
  await snap(page, 'builder-change-app')
})
