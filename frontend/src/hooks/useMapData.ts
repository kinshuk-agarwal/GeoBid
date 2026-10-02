import { useCallback, useEffect, useState } from 'react'

import { mapApi } from '@/api'
import { errorMessage } from '@/api/client'
import type { MapResponse } from '@/types'

export function useMapData(latitude: number, longitude: number, radiusKm: number) {
  const [data, setData] = useState<MapResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const ctrl = new AbortController()
    setLoading(true)
    setError(null)
    mapApi
      .poles({ latitude, longitude, radius_km: radiusKm, top_limit: 5 }, ctrl.signal)
      .then((d) => setData(d))
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(errorMessage(e, 'Could not load map data'))
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false)
      })
    return () => ctrl.abort()
  }, [latitude, longitude, radiusKm, reloadKey])

  const reload = useCallback(() => setReloadKey((k) => k + 1), [])
  return { data, loading, error, reload }
}
