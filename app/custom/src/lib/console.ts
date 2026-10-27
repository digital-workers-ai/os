const CONSOLE_URL: string = import.meta.env.VITE_CONSOLE_URL ?? 'http://localhost:3092'

export const consoleUrl = (path: string) => `${CONSOLE_URL}${path}`
