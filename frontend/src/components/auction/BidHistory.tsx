import type { Bid } from '@/types'
import { formatINR } from '@/utils/format'

function timeAgo(iso: string, clockOffset: number): string {
  const s = Math.max(0, Math.round((Date.now() + clockOffset - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

interface Props {
  bids: Bid[]
  reserve: number
  myId: number | null
  clockOffset: number
  /** bid that just arrived live; briefly highlighted */
  highlightId?: number | null
}

export function BidHistory({ bids, reserve, myId, clockOffset, highlightId }: Props) {
  if (bids.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center">
        <p className="text-sm font-medium">No bids yet</p>
        <p className="mt-1 text-xs text-slate-500">Bidding starts at the base price of {formatINR(reserve)}.</p>
      </div>
    )
  }
  const top = bids[0].amount
  return (
    <ol className="divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200">
      {bids.map((b, i) => {
        const mine = b.advertiser_id === myId
        return (
          <li
            key={b.id}
            className={`grid grid-cols-[1fr_auto] items-center gap-x-3 px-3 py-2 ${i === 0 ? 'bg-emerald-50/60' : ''} ${
              b.id === highlightId ? 'gb-flash' : ''
            }`}
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className={`text-sm font-semibold tabular-nums ${i === 0 ? 'text-slate-900' : 'text-slate-600'}`}>
                  {formatINR(b.amount)}
                </span>
                {i === 0 && (
                  <span className="rounded bg-emerald-600 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-white">
                    Leading
                  </span>
                )}
              </div>
              <div className="text-xs text-slate-500">
                {mine ? <span className="font-medium text-slate-900">You</span> : b.bidder_alias}
                <span className="mx-1">·</span>
                {timeAgo(b.timestamp, clockOffset)}
              </div>
            </div>
            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-slate-700" style={{ width: `${(100 * b.amount) / top}%` }} />
            </div>
          </li>
        )
      })}
    </ol>
  )
}
