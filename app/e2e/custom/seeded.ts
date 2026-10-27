import type { Page } from '@playwright/test'
import { expect } from '../fixtures'

export interface ShippedApp {
  title: string
  input: string[]
  roles: string[]
  lands_as: string
  code: 'script.py' | 'screen.tsx' | null
}

export const APPS: Record<string, ShippedApp> = {
  receipts: { title: 'Receipts', input: ['photo'], roles: ['staff', 'finance'], lands_as: 'expense', code: null },
  supplier_invoices: { title: 'Supplier invoices', input: ['photo', 'pdf'], roles: ['finance'], lands_as: 'bill', code: null },
  mileage_log: { title: 'Mileage log', input: ['photo'], roles: ['staff', 'finance'], lands_as: 'odometer_reading', code: 'script.py' },
  shelf_audit: { title: 'Shelf audit', input: ['photo'], roles: ['store_staff', 'manager'], lands_as: 'stock_check', code: 'script.py' },
  damage_claims: { title: 'Damage claims', input: ['photo'], roles: ['staff', 'manager'], lands_as: 'claim', code: null },
  check_deposits: { title: 'Check deposits', input: ['photo'], roles: ['finance'], lands_as: 'payment', code: null },
  equipment_checkout: { title: 'Equipment check-out', input: ['scan'], roles: ['staff'], lands_as: 'asset_move', code: null },
  inventory_count: { title: 'Inventory count', input: ['scan'], roles: ['store_staff', 'manager'], lands_as: 'stock_count', code: 'script.py' },
  event_check_in: { title: 'Event check-in', input: ['scan'], roles: ['staff'], lands_as: 'check_in', code: null },
  maintenance_tags: { title: 'Maintenance tags', input: ['scan'], roles: ['technician', 'manager'], lands_as: 'service_record', code: null },
  mailroom: { title: 'Mailroom', input: ['scan', 'photo'], roles: ['front_desk'], lands_as: 'package', code: null },
  batch_trace: { title: 'Batch trace', input: ['scan'], roles: ['production'], lands_as: 'batch_step', code: null },
  perio_charting: { title: 'Perio charting', input: ['voice'], roles: ['dentist', 'hygienist'], lands_as: 'perio_chart', code: null },
  property_inspection: { title: 'Property inspection', input: ['voice', 'photo'], roles: ['property_manager', 'inspector'], lands_as: 'inspection', code: null },
  vehicle_pre_trip: { title: 'Vehicle pre-trip check', input: ['voice'], roles: ['driver', 'fleet_manager'], lands_as: 'vehicle_check', code: null },
  food_safety_log: { title: 'Food safety log', input: ['voice'], roles: ['kitchen_staff', 'kitchen_manager'], lands_as: 'temperature_check', code: null },
  site_safety_walk: { title: 'Site safety walk', input: ['voice', 'photo'], roles: ['site_lead', 'safety_manager'], lands_as: 'safety_walk', code: null },
  sales_visit_debrief: { title: 'Sales visit debrief', input: ['voice'], roles: ['sales', 'head_of_sales'], lands_as: 'meeting', code: null },
  vet_visit_notes: { title: 'Vet visit notes', input: ['voice'], roles: ['vet', 'vet_tech'], lands_as: 'visit_note', code: null },
  field_service_report: { title: 'Field service report', input: ['voice'], roles: ['technician', 'dispatcher'], lands_as: 'ticket', code: null },
  proof_of_delivery: { title: 'Proof of delivery', input: ['photo'], roles: ['driver', 'dispatcher'], lands_as: 'delivery', code: 'screen.tsx' },
}

export interface RecordRow {
  id: string
  app: string
  fields: Record<string, unknown>
  saved_at: string | null
}

export interface Lookup {
  matches: { value: string; label: string }[]
  history: unknown[]
}

export async function listed(page: Page, app: string): Promise<RecordRow[]> {
  const response = await page.request.get(`/api/custom/records?${new URLSearchParams({ app })}`)
  await expect(response).toBeOK()
  return (await response.json()) as RecordRow[]
}

export async function seededRecord(page: Page, app: string, field: string, value: unknown): Promise<string> {
  const records = (await listed(page, app)).filter((record) => record.fields[field] === value)
  expect(records.length, `a seeded ${app} record with ${field} ${String(value)}`).toBeGreaterThan(0)
  return records[records.length - 1].id
}

export async function lookedUp(page: Page, app: string, field: string, q: string): Promise<Lookup> {
  const response = await page.request.get(`/api/custom/apps/${app}/lookup/${field}?${new URLSearchParams({ q })}`)
  await expect(response).toBeOK()
  return (await response.json()) as Lookup
}
