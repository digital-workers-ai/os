import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { type Heard, hearInTurn, holdToTalk, ready } from './ready'

const SITES = ['DB', 'B', 'MB', 'DL', 'L', 'ML']

const ITEMS = [
  'service_brakes',
  'parking_brake',
  'steering',
  'lights_and_reflectors',
  'tires',
  'horn',
  'wipers',
  'mirrors',
  'coupling_devices',
  'wheels_and_rims',
  'emergency_equipment',
]

const BUCCAL: Heard = {
  transcript: 'three, three two four, bleeding on the two',
  updates: [
    { row: '3', column: 'DB', field: 'depth', value: 3 },
    { row: '3', column: 'B', field: 'depth', value: 2 },
    { row: '3', column: 'MB', field: 'depth', value: 4 },
    { row: '3', column: 'B', field: 'bleeding', value: 'bleeding' },
  ],
  cursor: { row: '3', column: 'DL' },
  readback: 'Tooth 3: 3, 2, 4, bleeding on B',
}

const LINGUAL: Heard = {
  transcript: 'two three three',
  updates: [
    { row: '3', column: 'DL', field: 'depth', value: 2 },
    { row: '3', column: 'L', field: 'depth', value: 3 },
    { row: '3', column: 'ML', field: 'depth', value: 3 },
  ],
  cursor: { row: '4', column: 'DB' },
  readback: 'Tooth 3 lingual: 2, 3, 3. Tooth 4 next',
}

const CHECKED: Heard = {
  transcript: 'everything passes except the tires, front left tread low',
  updates: [
    ...ITEMS.map((item) => ({ section: 'vehicle', item, field: 'result', value: item === 'tires' ? 'fail' : 'pass' })),
    { section: 'vehicle', item: 'tires', field: 'defect', value: 'Front left tread low' },
  ],
  cursor: null,
  readback: 'Ten items pass. Tires fail: front left tread low',
}

const cursor = (page: Page) => page.locator('[data-testid^="grid-cell-"][aria-current="true"]')

const cell = (page: Page, row: number, column: string) => page.getByTestId(`grid-cell-${row}-${column}`)

const item = (page: Page, name: string) => page.getByTestId(`checklist-vehicle-${name}`)

test('the perio cursor moves with each utterance', async ({ page }) => {
  await hearInTurn(page, [BUCCAL, LINGUAL])
  await visit(page, '/apps/perio_charting/new')
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Perio charting')
  await expect(page.locator('[data-testid^="grid-cell-"]')).toHaveCount(32 * SITES.length)
  await expect(cursor(page)).toHaveCount(1)
  await expect(cell(page, 1, 'DB')).toHaveAttribute('aria-current', 'true')

  await holdToTalk(page)
  await expect(cell(page, 3, 'DB')).toContainText('3')
  await expect(cell(page, 3, 'B')).toContainText('2')
  await expect(cell(page, 3, 'MB')).toContainText('4')
  await expect(page.getByTestId('readback')).toHaveText(BUCCAL.readback)
  await expect(cursor(page)).toHaveCount(1)
  await expect(cell(page, 3, 'DL')).toHaveAttribute('aria-current', 'true')

  const second = await holdToTalk(page)
  expect(second.cursor).toEqual(BUCCAL.cursor)
  await expect(cell(page, 3, 'DL')).toContainText('2')
  await expect(cell(page, 3, 'L')).toContainText('3')
  await expect(cell(page, 3, 'ML')).toContainText('3')
  await expect(page.getByTestId('readback')).toHaveText(LINGUAL.readback)
  await expect(cursor(page)).toHaveCount(1)
  await expect(cell(page, 4, 'DB')).toHaveAttribute('aria-current', 'true')
  await ready(page)
  await snap(page, 'custom-perio-grid')
})

test('the vehicle checklist marks pass and fail', async ({ page }) => {
  await hearInTurn(page, [CHECKED])
  await visit(page, '/apps/vehicle_pre_trip/new')
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Vehicle pre-trip check')
  await expect(page.locator('[data-testid^="checklist-vehicle-"]')).toHaveCount(ITEMS.length)
  for (const name of ITEMS) await expect(item(page, name).getByRole('combobox')).toHaveValue('')

  await holdToTalk(page)
  for (const name of ITEMS) await expect(item(page, name).getByRole('combobox')).toHaveValue(name === 'tires' ? 'fail' : 'pass')
  await expect(item(page, 'tires').getByRole('textbox')).toHaveValue('Front left tread low')
  await expect(page.getByTestId('readback')).toHaveText(CHECKED.readback)
  await ready(page)
  await snap(page, 'custom-vehicle-checklist')
})

test('unsaved work survives a reload', async ({ page }) => {
  await visit(page, '/apps/vehicle_pre_trip/new')
  await ready(page)
  await page.getByTestId('field-vehicle').fill('Truck 9')
  await item(page, 'horn').getByRole('combobox').selectOption('pass')
  await item(page, 'tires').getByRole('combobox').selectOption('fail')
  await item(page, 'tires').getByRole('textbox').fill('Cracked sidewall')

  await page.reload()
  await ready(page)
  await expect(page.getByTestId('field-vehicle')).toHaveValue('Truck 9')
  await expect(item(page, 'horn').getByRole('combobox')).toHaveValue('pass')
  await expect(item(page, 'tires').getByRole('combobox')).toHaveValue('fail')
  await expect(item(page, 'tires').getByRole('textbox')).toHaveValue('Cracked sidewall')
  await expect(item(page, 'steering').getByRole('combobox')).toHaveValue('')
})
