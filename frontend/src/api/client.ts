import axios, { AxiosError } from 'axios'

const TOKEN_KEY = 'geobid.token'

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

// In development the Vite dev server proxies /api to the backend, so an empty
// base URL works. Set VITE_API_BASE_URL to call a backend on another origin.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export const api = axios.create({ baseURL: `${API_BASE_URL}/api` })

api.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/** Extract a human-readable message from an API error. */
export function errorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
    if (!err.response) return 'Cannot reach the GeoBid server. Is the backend running?'
  }
  return err instanceof Error ? err.message : fallback
}
