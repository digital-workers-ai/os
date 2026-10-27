import type { AppDefinition, Field, TemplateValues, Update, Values } from '@/api'

export const humanize = (name: string) => {
  const text = name.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export const labelsOf = (field: Field): string[] =>
  field.labels.map((label) => (Array.isArray(label) ? label[0] : String(label)))

export const meaningOf = (field: Field, label: string): string => {
  const entry = field.labels.find((entry) => Array.isArray(entry) && entry[0] === label)
  return Array.isArray(entry) ? entry[1] : ''
}

const EMPTY: TemplateValues = { rows: {}, cells: {}, items: {} }

export const blankValues = (app: AppDefinition): Values => (app.template ? { template: EMPTY } : {})

export const templateOf = (values: Values): TemplateValues => ({ ...EMPTY, ...(values.template as Partial<TemplateValues>) })

export const rowsOf = (values: Values, list: string): Values[] =>
  Array.isArray(values[list]) ? (values[list] as Values[]) : []

export const cellKey = (row: string | number, column: string) => `${row}:${column}`

export const itemKey = (section: string, item: string) => `${section}:${item}`

export function setPath(target: unknown, [head, ...rest]: (string | number)[], value: unknown): unknown {
  if (head === undefined) return value
  if (typeof head === 'number') {
    const list = Array.isArray(target) ? [...target] : []
    list[head] = setPath(list[head], rest, value)
    return list
  }
  const object = target && typeof target === 'object' && !Array.isArray(target) ? (target as Values) : {}
  return { ...object, [head]: setPath(object[head], rest, value) }
}

const setIn = (part: Record<string, Values>, key: string, field: string, value: unknown) => ({
  ...part,
  [key]: { ...part[key], [field]: value },
})

export function applyUpdates(values: Values, updates: Update[]): Values {
  return updates.reduce<Values>((next, { list, row, column, section, item, field, value }) => {
    if (list !== undefined) {
      const rows = [...rowsOf(next, list)]
      const index = Number(row)
      while (rows.length <= index) rows.push({})
      rows[index] = { ...rows[index], [field]: value }
      return { ...next, [list]: rows }
    }
    const template = templateOf(next)
    if (section !== undefined && item !== undefined)
      return { ...next, template: { ...template, items: setIn(template.items, itemKey(section, item), field, value) } }
    if (row !== undefined && column !== undefined)
      return { ...next, template: { ...template, cells: setIn(template.cells, cellKey(row, column), field, value) } }
    if (row !== undefined) return { ...next, template: { ...template, rows: setIn(template.rows, String(row), field, value) } }
    return { ...next, [field]: value }
  }, values)
}

export function applyScan(app: AppDefinition, values: Values, code: string): Values {
  return app.fields.reduce<Values>((next, field) => {
    if (field.from_scan) return { ...next, [field.name]: code }
    const scanned = field.fields.find((sub) => sub.from_scan)
    return scanned ? { ...next, [field.name]: [...rowsOf(next, field.name), { [scanned.name]: code }] } : next
  }, values)
}

const present = (value: unknown) => value !== null && value !== undefined

function mergeTemplate(current: TemplateValues, read: Partial<TemplateValues>): TemplateValues {
  const part = (mine: Record<string, Values>, theirs: Record<string, Values> = {}) => ({
    ...mine,
    ...Object.fromEntries(Object.entries(theirs).map(([key, entry]) => [key, { ...mine[key], ...entry }])),
  })
  return { rows: part(current.rows, read.rows), cells: part(current.cells, read.cells), items: part(current.items, read.items) }
}

export function merge(values: Values, read: Values): Values {
  return Object.entries(read).reduce<Values>(
    (next, [name, value]) =>
      !present(value)
        ? next
        : { ...next, [name]: name === 'template' ? mergeTemplate(templateOf(next), value as Partial<TemplateValues>) : value },
    values,
  )
}

const toNumber = (value: unknown) => {
  if (typeof value === 'number') return value
  const number = parseFloat(String(value ?? ''))
  return Number.isFinite(number) ? number : null
}

const filled = (entry: Values) =>
  Object.values(entry).some((value) => present(value) && !(Array.isArray(value) && value.length === 0))

function convert(field: Field, value: unknown): unknown {
  if (field.type === 'number' || field.type === 'money') return toNumber(value)
  if (field.type === 'many_of') return Array.isArray(value) ? value : []
  return value === '' || value === undefined ? null : value
}

function convertAll(fields: Field[], values: Values): Values {
  return Object.fromEntries(
    fields.map((field) => [
      field.name,
      field.type === 'list'
        ? rowsOf(values, field.name)
            .map((row) => convertAll(field.fields, row))
            .filter(filled)
        : convert(field, values[field.name]),
    ]),
  )
}

const convertPart = (entries: Record<string, Values>, fields: Field[] = []) =>
  Object.fromEntries(
    Object.entries(entries)
      .map(([key, entry]) => [key, convertAll(fields, entry)] as const)
      .filter(([, entry]) => filled(entry)),
  )

export function toPayload(app: AppDefinition, values: Values): Values {
  const fields = convertAll(app.fields, values)
  const template = app.template
  if (!template) return fields
  const entered = templateOf(values)
  return {
    ...fields,
    template:
      template.kind === 'grid'
        ? { rows: convertPart(entered.rows, template.rows?.fields), cells: convertPart(entered.cells, template.cells?.fields) }
        : { items: convertPart(entered.items, template.items?.fields) },
  }
}

const shown = (value: unknown) => (Array.isArray(value) ? value.join(', ') : String(value))

export function summary(app: AppDefinition, values: Values): string[] {
  return app.fields.flatMap((field) => {
    const value = values[field.name]
    if (field.type === 'list') {
      const count = rowsOf(values, field.name).length
      return count ? [`${humanize(field.name)}: ${count}`] : []
    }
    if (field.type === 'photo' || field.type === 'screen' || !present(value) || value === '') return []
    if (Array.isArray(value) && value.length === 0) return []
    return [shown(value)]
  })
}
