export const stamp = (iso: string) => new Date(iso).toISOString().slice(0, 16).replace('T', ' ')

export const day = (iso: string) => new Date(iso).toISOString().slice(0, 10)
