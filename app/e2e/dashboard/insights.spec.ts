import type { Page } from '@playwright/test'
import { expect, mockJson, NOW, snap, test, visit } from '../fixtures'
import { ready } from './ready'

interface PageSpec {
  goals: boolean
  findings: boolean
}

interface Goals {
  goals: unknown[]
  met: number
  missed: number
  unknown: number
}

interface Rules {
  findings: unknown[]
  by_severity: Record<string, number>
}

const GOALS_PAGE = 5
const FINDINGS_PAGE = 10

const option = (page: Page, severity: string) => page.locator(`[data-testid="findings-filter-option"][data-severity="${severity}"]`)
const rows = (page: Page, table: string) => page.getByTestId(table).locator('tbody tr')

async function declared(page: Page) {
  const { dashboards } = await (await page.request.get('/api/definitions/dashboards')).json()
  const found = Object.entries<PageSpec>(dashboards).find(([, spec]) => spec.findings && spec.goals)
  test.skip(!found, 'no page declares goals and findings')
  return found![0]
}

test('goals and findings', async ({ page }) => {
  const name = await declared(page)
  const goals: Goals = await (await page.request.get('/api/insights/goals')).json()
  const rules: Rules = await (await page.request.get('/api/insights/rules')).json()
  await visit(page, `/${name}`)
  const pills = page.getByTestId('goals-pills')
  await expect(pills).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId('findings-filter')).toBeVisible({ timeout: 20_000 })
  await expect(pills).toContainText(`${goals.met} met`)
  await expect(pills).toContainText(`${goals.missed} missed`)
  await expect(pills).toContainText(`${goals.unknown} unknown`)
  await expect(rows(page, 'goals-table')).toHaveCount(Math.min(goals.goals.length, GOALS_PAGE))
  const total = rules.findings.length
  await expect(option(page, 'all')).toHaveAttribute('aria-pressed', 'true')
  await expect(option(page, 'all')).toContainText(String(total))
  for (const [severity, n] of Object.entries(rules.by_severity)) await expect(option(page, severity)).toContainText(String(n))
  const findings = rows(page, 'findings-table')
  await expect(findings).toHaveCount(Math.min(total, FINDINGS_PAGE))
  await option(page, 'high').click()
  await expect(option(page, 'high')).toHaveAttribute('aria-pressed', 'true')
  await expect(findings).toHaveCount(Math.min(rules.by_severity.high ?? 0, FINDINGS_PAGE))
  await expect(page.locator('[data-testid="findings-table"] tbody tr:not([data-severity="high"])')).toHaveCount(0)
  await option(page, 'high').click()
  await expect(option(page, 'all')).toHaveAttribute('aria-pressed', 'true')
  await expect(findings).toHaveCount(Math.min(total, FINDINGS_PAGE))
  const section = page.getByTestId('findings')
  await expect(section.getByTestId('pager')).toHaveCount(total > FINDINGS_PAGE ? 1 : 0)
  if (total > FINDINGS_PAGE) {
    const range = section.getByTestId('pager-range')
    const first = await range.textContent()
    await section.getByTestId('pager-next').click()
    await expect(range).not.toHaveText(first!)
    await section.getByTestId('pager-prev').click()
    await expect(range).toHaveText(first!)
  }
  await ready(page)
  await snap(page, 'dashboard-insights')
})

test('empty', async ({ page }) => {
  const name = await declared(page)
  await mockJson(page, '**/api/insights/rules', {
    as_of: NOW.toISOString(),
    rules: 0,
    findings: [],
    by_severity: { high: 0, medium: 0, low: 0 },
    report: { evaluated: 0, unreadable: {} },
  })
  await mockJson(page, '**/api/insights/goals', { goals: [], met: 0, missed: 0, unknown: 0 })
  await visit(page, `/${name}`)
  await expect(page.getByTestId('goals-empty')).toHaveText('no goals')
  await expect(page.getByTestId('findings-empty')).toHaveText('no findings')
})
