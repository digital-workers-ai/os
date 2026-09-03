import { createContext } from 'react'

export interface PageTitleValue {
  title: string
  subtitle?: string
}

export const SetPageTitleContext = createContext<((v: PageTitleValue) => void) | null>(null)
