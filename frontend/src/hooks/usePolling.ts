import { useCallback, useEffect, useRef, useState } from 'react'

import { errorMessage } from '@/api/client'

/** Load data and refresh it every ``ms`` while the page is visible. */
export function usePolling<T>(load: () => Promise<T>, deps: unknown[], ms = 15_000) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const loadRef = useRef(load)
  loadRef.current = load

  const refresh = useCallback(async () => {
    try {
      setData(await loadRef.current())
      setError(null)
    } catch (e) {
      setError(errorMessage(e, 'Could not load data'))
    }
  }, [])

  useEffect(() => {
    void refresh()
    const t = setInterval(() => document.visibilityState === 'visible' && void refresh(), ms)
    return () => clearInterval(t)
  }, [refresh, ms, ...deps]) // reload when the caller's inputs change

  return { data, error, refresh }
}
