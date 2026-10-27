import type { Page } from '@playwright/test'
import { expect, mockJson, snap, test, visit } from '../fixtures'
import { PHOTO, ready } from './ready'

interface Message {
  role: 'person' | 'builder'
  text: string
}

interface Turn {
  reply: string
  questions: string[]
  draft: string | null
  problems: string[]
}

const DESCRIPTION = 'We pour concrete and want every pour logged with a photo of the slump test.'

const QUESTIONS = ['Which mixes do you pour?', 'Who logs the pours?', 'Should each pour name its job site?']

const ANSWERS = ['Standard, high strength and fiber', 'The site lead', 'Yes, by the site name']

const DRAFT = [
  'title: Concrete pours',
  'description: A photo of the slump test at a concrete pour.',
  'input: photo',
  'roles: [site_lead]',
  'lands_as: pour',
  'fields:',
  '  site: { type: text }',
  '  slump: { type: number, unit: in }',
  '  mix: { type: one_of, labels: [standard, high_strength, fiber] }',
].join('\n')

const ASKED: Turn = { reply: 'Three questions before I draft it.', questions: QUESTIONS, draft: null, problems: [] }

const DRAFTED: Turn = { reply: 'Here is the draft. Try it on a sample photo.', questions: [], draft: DRAFT, problems: [] }

const TRIED = { fields: { site: 'Elm Street', slump: 4, mix: 'standard' }, missing: [] }

const ISSUE = { number: 41, url: 'https://github.com/digital-workers-ai/os/issues/41' }

async function builder(page: Page) {
  let next = 0
  const turns = [ASKED, DRAFTED]
  await page.route('**/api/builder/turns', (r) => r.fulfill({ json: turns[Math.min(next++, turns.length - 1)] }))
  await mockJson(page, '**/api/builder/try', TRIED)
  await mockJson(page, '**/api/builder/submit', ISSUE)
}

const sent = (page: Page, path: string) => page.waitForRequest((r) => r.url().endsWith(`/api/builder/${path}`) && r.method() === 'POST')

async function described(page: Page): Promise<Message[]> {
  await visit(page, '/new-app')
  await ready(page)
  const turn = sent(page, 'turns')
  await page.getByTestId('builder-input').fill(DESCRIPTION)
  await page.getByTestId('builder-send').click()
  return ((await turn).postDataJSON() as { messages: Message[] }).messages
}

test('the builder asks every question in one round', async ({ page }) => {
  await builder(page)
  const messages = await described(page)
  expect(messages).toEqual([{ role: 'person', text: DESCRIPTION }])
  const questions = page.getByTestId('builder-questions')
  await expect(questions).toBeVisible()
  for (const question of QUESTIONS) await expect(questions.getByLabel(question)).toBeEditable()
  await expect(questions.getByRole('textbox')).toHaveCount(QUESTIONS.length)
  await expect(page.getByTestId('page-main')).toContainText(ASKED.reply)
  await expect(page.getByTestId('builder-preview')).toHaveCount(0)
  await expect(page.getByTestId('builder-submit')).toHaveCount(0)
  await ready(page)
  await snap(page, 'custom-new-app-questions')
})

test('answers build a preview, Try it reads a sample, and submit links the issue', async ({ page }) => {
  await builder(page)
  await described(page)
  const questions = page.getByTestId('builder-questions')
  for (const [n, question] of QUESTIONS.entries()) await questions.getByLabel(question).fill(ANSWERS[n])
  const answered = sent(page, 'turns')
  await page.getByTestId('builder-send').click()
  const messages = ((await answered).postDataJSON() as { messages: Message[] }).messages
  expect(messages[0]).toEqual({ role: 'person', text: DESCRIPTION })
  expect(messages[1].role).toBe('builder')
  expect(messages.at(-1)!.role).toBe('person')
  for (const answer of ANSWERS) expect(messages.at(-1)!.text).toContain(answer)

  const preview = page.getByTestId('builder-preview')
  await expect(preview).toBeVisible()
  for (const text of ['Concrete pours', 'slump', 'mix']) await expect(preview).toContainText(text)
  await ready(page)
  await snap(page, 'custom-new-app-preview')

  await page.locator('input[type="file"]').setInputFiles(PHOTO)
  const tried = sent(page, 'try')
  await page.getByTestId('builder-try').click()
  const sample = (await tried).postDataJSON() as { draft: string; files: { media_type: string; data: string }[] }
  expect(sample.draft).toBe(DRAFT)
  expect(sample.files).toHaveLength(1)
  expect(sample.files[0].media_type).toBe('image/jpeg')
  await expect(page.getByTestId('page-main')).toContainText('Elm Street')

  const submitted = sent(page, 'submit')
  await page.getByTestId('builder-submit').click()
  expect((await submitted).postDataJSON()).toEqual({ description: DESCRIPTION, answers: ANSWERS, draft: DRAFT })
  const link = page.getByTestId('builder-issue-link')
  await expect(link).toHaveAttribute('href', ISSUE.url)
  await expect(link).toContainText(`#${ISSUE.number}`)
  await ready(page)
  await snap(page, 'custom-new-app-issue')
})
