import { ArrowLeft, MapPinned } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'

import { polesApi } from '@/api'
import { errorMessage } from '@/api/client'
import { Spinner } from '@/components/common/Spinner'
import { PoleAnalysis } from '@/components/pole/PoleAnalysis'
import { PoleDetails } from '@/components/pole/PoleDetails'
import { useAuth } from '@/hooks/useAuth'
import type { Pole } from '@/types'

export function PoleDetailsPage() {
  const { id = '' } = useParams()
  const { user } = useAuth()
  const analyst = user?.role === 'ADMIN'
  const [pole, setPole] = useState<Pole | null>(null)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setPole(null)
    setError(null)
    Promise.all([polesApi.get(id), polesApi.list()])
      .then(([p, all]) => {
        setPole(p)
        setTotal(all.length)
      })
      .catch((e) => setError(errorMessage(e, 'Could not load pole')))
  }, [id])

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-xl px-4 py-6">
        <div className="mb-4 flex items-center justify-between text-sm">
          <Link to="/map" className="inline-flex items-center gap-1.5 text-slate-600 hover:text-slate-900">
            <ArrowLeft className="size-4" /> Back to map
          </Link>
          {pole && (
            <Link
              to={`/map?pole=${pole.code}`}
              className="inline-flex items-center gap-1.5 font-medium text-slate-700 hover:text-slate-900"
            >
              <MapPinned className="size-4" /> Show on map
            </Link>
          )}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          {error ? (
            <p className="text-sm text-red-700">{error}</p>
          ) : !pole ? (
            <div className="flex justify-center py-10">
              <Spinner className="size-6" />
            </div>
          ) : (
            analyst ? (
              <PoleAnalysis pole={pole} totalPoles={total} standalone />
            ) : (
              <PoleDetails pole={pole} totalPoles={total} standalone />
            )
          )}
        </div>
      </div>
    </div>
  )
}
