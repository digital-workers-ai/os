import { expect, mockJson, NOW, snap, test, visit } from './fixtures'

const countPill = (name: string) => new RegExp(`^[\\d,]+ ${name}$`)

test('default', async ({ page }) => {
  await visit(page, '/')
  await expect(page.getByTestId('page-heading')).toHaveText('Insights')
  const goalsPills = page.getByTestId('goals-pills')
  for (const verdict of ['met', 'missed', 'unknown']) await expect(goalsPills.getByText(countPill(verdict))).toBeVisible()
  const findingsPills = page.getByTestId('findings-pills')
  for (const severity of ['high', 'medium', 'low']) await expect(findingsPills.getByText(countPill(severity))).toBeVisible()
  await snap(page, 'home-default')
})

test('show all', async ({ page }) => {
  await visit(page, '/')
  const goalsAll = page.getByTestId('goals').getByTestId('pager-all')
  if (await goalsAll.count()) {
    await goalsAll.click()
    await expect(goalsAll).toHaveText('Paginate')
    await snap(page, 'home-goals-all')
  }
  const findingsAll = page.getByTestId('findings').getByTestId('pager-all')
  await findingsAll.click()
  await expect(findingsAll).toHaveText('Paginate')
  await snap(page, 'home-findings-all')
})

test('next page of findings', async ({ page }) => {
  await visit(page, '/')
  const findings = page.getByTestId('findings')
  const next = findings.getByTestId('pager-next')
  test.skip(!(await next.count()) || !(await next.isEnabled()), 'findings fit on one page')
  await next.click()
  await expect(findings.getByTestId('pager-prev')).toBeEnabled()
  await snap(page, 'home-findings-page-2')
})

test('empty', async ({ page }) => {
  await mockJson(page, '**/api/insights/goals', { goals: [], met: 0, missed: 0, unknown: 0 })
  await mockJson(page, '**/api/insights/rules', {
    as_of: NOW.toISOString(),
    rules: 0,
    findings: [],
    by_severity: {},
    report: { evaluated: 0, unreadable: {} },
  })
  await visit(page, '/')
  await expect(page.getByTestId('goals').getByTestId('empty')).toHaveText('no goals defined')
  await expect(page.getByTestId('findings').getByTestId('empty')).toHaveText('no findings')
  await snap(page, 'home-empty')
})

test('error', async ({ page }) => {
  await mockJson(page, '**/api/insights/goals', { detail: 'boom' }, 500)
  await mockJson(page, '**/api/insights/rules', { detail: 'boom' }, 500)
  await visit(page, '/')
  await expect(page.getByTestId('goals').getByTestId('error-banner')).toBeVisible()
  await expect(page.getByTestId('findings').getByTestId('error-banner')).toBeVisible()
  await snap(page, 'home-error')
})
