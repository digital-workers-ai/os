import { createContext, type ReactNode } from 'react'

export const SetPageTitleContext = createContext<((title: string) => void) | null>(null)
export const SetPageBadgeContext = createContext<((badge: ReactNode) => void) | null>(null)
