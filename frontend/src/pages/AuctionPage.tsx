import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'

import { AuctionLive } from '@/components/auction/AuctionLive'

/** Full-page view of one auction (deep links; the map uses the bid popup). */
export function AuctionPage() {
  const { id = '' } = useParams()
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl px-4 py-6">
        <Link to="/map" className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900">
          <ArrowLeft className="size-4" /> Back to map
        </Link>
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <AuctionLive auctionId={id} full />
        </div>
      </div>
    </div>
  )
}
