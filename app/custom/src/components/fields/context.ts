import { createContext, useContext } from 'react'
import type { AppDefinition, Field, RecordFile, Sent } from '@/api'

export type Path = (string | number)[]

export interface Form {
  app: AppDefinition
  record: string | null
  files: RecordFile[]
  upload: (file: Sent) => Promise<RecordFile>
  set: (path: Path, value: unknown) => void
}

export const FormContext = createContext<Form | null>(null)

export function useForm(): Form {
  const form = useContext(FormContext)
  if (!form) throw new Error('fields render inside a FormContext')
  return form
}

export interface ControlProps {
  field: Field
  value: unknown
  onChange: (value: unknown) => void
  path: string
  file: string
  id?: string
  label?: string
  testId?: string
  disabled?: boolean
}

export const text = (value: unknown) => (value === null || value === undefined ? '' : String(value))
