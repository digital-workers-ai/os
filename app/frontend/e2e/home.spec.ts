import type { Page } from '@playwright/test'
import { expect, mockJson, NOW, snap, test, visit } from './fixtures'

const card = (page: Page, title: string) => page.locator('.bg-card').filter({ has: page.getByRole('heading', { name: title, exact: true }) })
const countPill = (name: string) => new RegExp(`^[\\d,]+ ${name}$`)

test('default', async ({ page }) => {
  await visit(page, '/')
  await expect(page.getByRole('heading', { name: 'Insights' })).toBeVisible()
  const goals = card(page, 'Goals')
  for (const verdict of ['met', 'missed', 'unknown']) await expect(goals.getByText(countPill(verdict))).toBeVisible()
  const findings = card(page, 'Findings')
  for (const severity of ['high', 'medium', 'low']) await expect(findings.getByText(countPill(severity))).toBeVisible()
  await snap(page, 'home-default')
})

test('show all', async ({ page }) => {
  await visit(page, '/')
  const goals = card(page, 'Goals')
  const goalsShowAll = goals.getByRole('button', { name: 'Show all' })
  if (await goalsShowAll.count()) {
    await goalsShowAll.click()
    await expect(goals.getByRole('button', { name: 'Paginate' })).toBeVisible()
    await snap(page, 'home-goals-all')
  }
  const findings = card(page, 'Findings')
  await findings.getByRole('button', { name: 'Show all' }).click()
  await expect(findings.getByRole('button', { name: 'Paginate' })).toBeVisible()
  await snap(page, 'home-findings-all')
})

test('next page of findings', async ({ page }) => {
  await visit(page, '/')
  const findings = card(page, 'Findings')
  const next = findings.getByRole('button', { name: 'Next →' })
  test.skip(!(await next.count()) || !(await next.isEnabled()), 'findings fit on one page')
  await next.click()
  await expect(findings.getByRole('button', { name: '← Prev' })).toBeEnabled()
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
  await expect(page.getByText('no goals defined')).toBeVisible()
  await expect(page.getByText('no findings')).toBeVisible()
  await snap(page, 'home-empty')
})

test('error', async ({ page }) => {
  await mockJson(page, '**/api/insights/goals', { detail: 'boom' }, 500)
  await mockJson(page, '**/api/insights/rules', { detail: 'boom' }, 500)
  await visit(page, '/')
  await expect(page.getByRole('alert')).toHaveCount(2)
  await snap(page, 'home-error')
})
