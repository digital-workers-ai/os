import { createContext } from 'react'

export interface PageHeading {
  title: string
  description?: string
}

export const SetPageTitleContext = createContext<((heading: PageHeading) => void) | null>(null)
