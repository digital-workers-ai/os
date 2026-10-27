import type { Page } from '@playwright/test'
import { expect, snap, test, visit } from '../fixtures'
import { PHOTO } from '../custom/ready'
import { builder, ISSUE, mockBuilder, opened, person, ready, say, sent, THREAD_ID, turned } from './ready'

const DESCRIPTION = 'We pour concrete and want every pour logged with a photo of the slump test.'

const QUESTIONS = ['Which mixes do you pour?', 'Who logs the pours?', 'Who supplies the concrete?']

const ANSWERS = ['Standard, high strength and fiber', 'The site lead', 'A ready-mix vendor, named on the ticket']

const ANSWERED = QUESTIONS.map((question, n) => `${question}\n${ANSWERS[n]}`).join('\n\n')

const OPTIONAL = 'Make the vendor optional'

const TRUCK = 'Add the truck number from the ticket'

const draft = (...fields: string[]) =>
  [
    'title: Concrete pours',
    'description: A photo of the slump test at a concrete pour.',
    'input: photo',
    'roles: [site_lead]',
    'lands_as: pour',
    'fields:',
    '  site: { type: text }',
    ...fields,
    '  slump: { type: number, unit: in }',
    '  mix: { type: one_of, labels: [standard, high_strength, fiber] }',
  ].join('\n')

const VENDOR = '  vendor: { type: text }'

const OPTIONAL_VENDOR = '  vendor: { type: text, description: Leave it blank when the concrete is mixed on site }'

const DRAFT = draft(VENDOR)

const REPLIES = [
  builder('Three questions before I draft it.', { questions: QUESTIONS }),
  builder('Here is the draft. Try it on a sample photo.', { draft: DRAFT }),
  builder('The vendor is optional now.', { draft: draft(OPTIONAL_VENDOR) }),
  builder('Added the truck number.', { draft: draft(OPTIONAL_VENDOR, '  truck: { type: text }') }),
]

const BUSINESS = 'We run a dental practice: a dentist, two hygienists and a front desk.'

const PROBLEM = "fields.strip type 'pass_fail' is not one of ['text', 'number', 'money', 'date', 'one_of', 'many_of', 'lookup', 'photo', 'list', 'screen']"

const STERILIZER = [
  'title: Sterilizer log',
  'description: A photo of the indicator strip after each autoclave cycle.',
  'input: photo',
  'roles: [hygienist]',
  'lands_as: sterilizer_cycle',
  'fields:',
  '  cycle: { type: number }',
  '  strip: { type: pass_fail }',
].join('\n')

const SUGGESTED = [
  builder('One app here already fits, and one would be new.', {
    suggestions: [
      { app: 'perio_charting', title: 'Perio charting', reason: 'Your hygienists chart pocket depths by voice.' },
      { app: null, title: 'Sterilizer log', reason: 'Log each autoclave cycle with a photo of its indicator strip.' },
    ],
  }),
  builder('A first draft of the sterilizer log.', { draft: STERILIZER, problems: [PROBLEM] }),
]

const READING = { fields: { site: 'Elm Street', vendor: null, slump: 4, mix: 'standard' }, missing: ['vendor'] }

const turns = (page: Page) => page.getByTestId('turn')

async function started(page: Page) {
  await visit(page, '/new')
  await opened(page)
}

test('New app starts a thread and the builder asks every question in one round', async ({ page }) => {
  await mockBuilder(page, { replies: REPLIES })
  await visit(page, '/')
  await ready(page)
  const thread = sent(page, 'threads')
  await page.getByRole('link', { name: 'New app' }).click()
  expect((await thread).postDataJSON()).toEqual({})
  await opened(page)
  await expect(page.getByTestId('thread')).toContainText('New app')
  await expect(page.getByTestId('turns-empty')).toBeVisible()

  expect(await say(page, DESCRIPTION)).toEqual({ text: DESCRIPTION })
  await expect(page.getByTestId('composer-input')).toHaveValue('')
  await expect(turns(page)).toHaveCount(2)
  await expect(turns(page).nth(0)).toHaveAttribute('data-role', 'person')
  await expect(turns(page).nth(0)).toContainText(DESCRIPTION)
  await expect(turns(page).nth(1)).toHaveAttribute('data-role', 'builder')
  await expect(turns(page).nth(1)).toContainText(REPLIES[0].text)
  const questions = page.getByTestId('builder-questions')
  for (const question of QUESTIONS) await expect(questions.getByLabel(question)).toBeEditable()
  await expect(questions.getByRole('textbox')).toHaveCount(QUESTIONS.length)
  await expect(page.getByTestId('builder-draft')).toHaveCount(0)
  await expect(page.getByTestId('builder-submit')).toHaveCount(0)
  await ready(page)
  await snap(page, 'builder-new-app-questions')
})

test('answers bring a draft and each change revises it, across a reload', async ({ page }) => {
  await mockBuilder(page, { replies: REPLIES })
  await started(page)
  await say(page, DESCRIPTION)
  const questions = page.getByTestId('builder-questions')
  for (const [n, question] of QUESTIONS.entries()) await questions.getByLabel(question).fill(ANSWERS[n])
  const answered = turned(page)
  await page.getByTestId('builder-answer').click()
  expect((await answered).postDataJSON()).toEqual({ text: ANSWERED })
  const card = page.getByTestId('builder-draft')
  await expect(card).toContainText(VENDOR.trim())
  await expect(page.getByTestId('builder-questions')).toHaveCount(0)
  await expect(turns(page)).toHaveCount(4)
  for (const answer of ANSWERS) await expect(turns(page).nth(2)).toContainText(answer)
  await expect(page.getByTestId('thread')).toContainText('Concrete pours')
  await ready(page)
  await snap(page, 'builder-new-app-draft')

  expect(await say(page, OPTIONAL)).toEqual({ text: OPTIONAL })
  await expect(card).toContainText('mixed on site')
  await expect(card).not.toContainText(VENDOR.trim())
  await expect(page.getByTestId('builder-draft')).toHaveCount(1)

  await page.reload()
  await ready(page)
  const said = [DESCRIPTION, REPLIES[0].text, ANSWERS[2], REPLIES[1].text, OPTIONAL, REPLIES[2].text]
  await expect(turns(page)).toHaveCount(said.length)
  for (const [n, text] of said.entries()) await expect(turns(page).nth(n)).toContainText(text)
  for (const question of QUESTIONS) await expect(turns(page).nth(1)).toContainText(question)
  await expect(page.getByTestId('builder-questions')).toHaveCount(0)
  await expect(card).toContainText('mixed on site')
  await expect(page.getByTestId('composer-input')).toHaveValue('')

  expect(await say(page, TRUCK)).toEqual({ text: TRUCK })
  await expect(turns(page)).toHaveCount(8)
  await expect(card).toContainText('truck: { type: text }')
  await expect(card).toContainText('mixed on site')
  await ready(page)
  await snap(page, 'builder-new-app-revised')
})

test('a business description gets suggestions: Draft it drafts the new one, Open goes to the one here', async ({ page }) => {
  await mockBuilder(page, { replies: SUGGESTED })
  await started(page)
  await say(page, BUSINESS)
  const cards = page.getByTestId('suggestion')
  await expect(cards).toHaveCount(2)
  await expect(cards.nth(0)).toContainText('Perio charting')
  await expect(cards.nth(0)).toContainText('Your hygienists chart pocket depths by voice.')
  await expect(cards.nth(0).getByRole('link', { name: 'Open' })).toHaveAttribute('href', '/apps/perio_charting')
  await expect(cards.nth(0).getByRole('button', { name: 'Draft it' })).toHaveCount(0)
  await expect(cards.nth(1)).toContainText('Sterilizer log')
  await expect(cards.nth(1).getByRole('link', { name: 'Open' })).toHaveCount(0)
  await ready(page)
  await snap(page, 'builder-suggestions')

  const drafting = turned(page)
  await cards.nth(1).getByRole('button', { name: 'Draft it' }).click()
  expect((await drafting).postDataJSON()).toEqual({ text: 'Draft the Sterilizer log app' })
  await expect(turns(page)).toHaveCount(4)
  await expect(page.getByTestId('builder-draft')).toContainText('title: Sterilizer log')
  await expect(page.getByTestId('builder-problems')).toContainText(PROBLEM)
  await expect(page.getByTestId('builder-submit')).toBeDisabled()

  await cards.nth(0).getByRole('link', { name: 'Open' }).click()
  await expect(page).toHaveURL(/\/apps\/perio_charting$/)
  await ready(page)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Perio charting')
})

test('Try it reads a sample, and Send for review files the thread for good', async ({ page }) => {
  await mockBuilder(page, { turns: [person(DESCRIPTION), REPLIES[1]], reading: READING })
  await visit(page, `/threads/${THREAD_ID}`)
  await ready(page)
  await expect(page.getByTestId('builder-draft')).toContainText('title: Concrete pours')

  await page.locator('input[type="file"]').setInputFiles(PHOTO)
  const tried = sent(page, `threads/${THREAD_ID}/try`)
  await page.getByTestId('builder-try').click()
  const sample = (await tried).postDataJSON() as { files: { name: string; media_type: string; data: string }[]; text: string | null }
  expect(sample.files).toHaveLength(1)
  expect(sample.files[0].name).toBe('receipt.jpg')
  expect(sample.files[0].media_type).toBe('image/jpeg')
  expect(sample.files[0].data).toMatch(/^\/9j\//)
  expect(sample.text).toBeNull()
  const reading = page.getByTestId('builder-reading')
  for (const text of ['Site', 'Elm Street', 'Slump', '4', 'Mix', 'standard', 'Not found: Vendor']) await expect(reading).toContainText(text)
  await ready(page)
  await snap(page, 'builder-try')

  const filed = sent(page, `threads/${THREAD_ID}/submit`)
  await page.getByTestId('builder-submit').click()
  expect((await filed).postData()).toBeNull()
  const link = page.getByTestId('builder-issue-link')
  await expect(link).toHaveAttribute('href', ISSUE.url)
  await expect(link).toContainText(`#${ISSUE.number}`)
  await expect(page.getByTestId('builder-submit')).toHaveCount(0)
  await expect(page.getByTestId('composer')).toHaveCount(0)

  await page.reload()
  await ready(page)
  await expect(page.getByTestId('builder-issue-link')).toHaveAttribute('href', ISSUE.url)
  await expect(page.getByTestId('builder-submit')).toHaveCount(0)
  await expect(page.getByTestId('composer')).toHaveCount(0)
  await expect(page.getByTestId('thread')).toContainText('Sent for review')
  await ready(page)
  await snap(page, 'builder-filed')
})

test('New app says so when the builder is off', async ({ page }) => {
  await visit(page, '/new')
  await ready(page)
  await expect(page.getByTestId('error-banner')).toContainText('409 the builder is off: set BUILDER_ENABLED')
  await expect(page).toHaveURL(/\/new$/)
})
