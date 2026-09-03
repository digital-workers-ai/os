import { createContext } from 'react'

export const SetPageTitleContext = createContext<((title: string) => void) | null>(null)
