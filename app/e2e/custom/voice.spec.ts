import { expect, snap, test, visit } from '../fixtures'
import { type Heard, hearInTurn, holdToTalk, ready } from './ready'

const COOLER: Heard = {
  transcript: 'walk-in cooler, 37',
  updates: [
    { list: 'readings', row: 0, field: 'unit', value: 'walk_in_cooler' },
    { list: 'readings', row: 0, field: 'temperature', value: 37 },
  ],
  cursor: { list: 'readings', row: 1 },
  readback: 'Walk-in cooler, 37°F',
}

const FREEZER: Heard = {
  transcript: 'freezer, 5',
  updates: [
    { list: 'readings', row: 1, field: 'unit', value: 'freezer' },
    { list: 'readings', row: 1, field: 'temperature', value: 5 },
  ],
  cursor: { list: 'readings', row: 2 },
  readback: 'Freezer, 5°F. Warning: above 0°F, say what was done about it',
}

test('hold to talk adds readings with a readback, a warning and undo', async ({ page }) => {
  await hearInTurn(page, [COOLER, FREEZER])
  await visit(page, '/apps/food_safety_log/new')
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Food safety log')
  await expect(page.getByTestId('field-shift')).toHaveValue('')
  await expect(page.getByTestId('field-readings-0-unit')).toHaveCount(0)
  await expect(page.getByTestId('talk')).toHaveAttribute('aria-pressed', 'false')

  const first = await holdToTalk(page)
  expect(first.audio.media_type).toMatch(/^audio\/(webm|mp4)/)
  expect(first.audio.data.length).toBeGreaterThan(0)
  await expect(page.getByTestId('field-readings-0-unit')).toHaveValue('walk_in_cooler')
  await expect(page.getByTestId('field-readings-0-temperature')).toHaveValue('37')
  await expect(page.getByTestId('readback')).toHaveText(COOLER.readback)

  const second = await holdToTalk(page)
  expect(second.cursor).toEqual(COOLER.cursor)
  await expect(page.getByTestId('field-readings-1-unit')).toHaveValue('freezer')
  await expect(page.getByTestId('field-readings-1-temperature')).toHaveValue('5')
  await expect(page.getByTestId('readback')).toHaveText(FREEZER.readback)
  await expect(page.getByTestId('field-readings-0-unit')).toHaveValue('walk_in_cooler')
  await ready(page)
  await snap(page, 'custom-voice-readings')

  await page.getByTestId('undo').click()
  await expect(page.getByTestId('field-readings-1-unit')).toHaveCount(0)
  await expect(page.getByTestId('field-readings-0-unit')).toHaveValue('walk_in_cooler')
  await expect(page.getByTestId('field-readings-0-temperature')).toHaveValue('37')
})
