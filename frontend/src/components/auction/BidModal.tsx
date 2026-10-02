import { ExternalLink, X } from 'lucide-react'
import { useEffect } from 'react'
import { Link } from 'react-router'

import { AuctionLive } from './AuctionLive'

/** Bid in a popup over the map instead of navigating away. */
export function BidModal({ auctionId, onClose }: { auctionId: number; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-[1500] flex items-end justify-center bg-slate-900/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Place a bid"
        onClick={(e) => e.stopPropagation()}
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:max-w-md sm:rounded-2xl"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-500">Place a bid</h2>
          <div className="flex items-center gap-1">
            <Link
              to={`/auctions/${auctionId}`}
              title="Open full auction page"
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            >
              <ExternalLink className="size-4" />
            </Link>
            <button onClick={onClose} aria-label="Close" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <X className="size-4" />
            </button>
          </div>
        </div>
        <AuctionLive auctionId={String(auctionId)} />
      </div>
    </div>
  )
}
