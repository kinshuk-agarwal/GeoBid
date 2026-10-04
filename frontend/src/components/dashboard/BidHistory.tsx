import { useCallback, useEffect, useState } from 'react'

import { dashboardApi } from '@/api'
import { errorMessage } from '@/api/client'
import type { BidHistoryRow, BidOutcome } from '@/types'
import { formatINR } from '@/utils/format'

import { CategoryDot } from '../common/CategoryBadge'
import { shortDate } from './AuctionTable'
import { Empty } from './Kpi'

const PAGE = 25

const OUTCOME: Record<BidOutcome, { label: (r: BidHistoryRow) => string; className: string }> = {
  WON: { label: (r) => `Won · seat ${r.seat}`, className: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  HOLDING: { label: (r) => `Holding seat ${r.seat}`, className: 'bg-sky-50 text-sky-800 ring-sky-200' },
  OUTBID: { label: () => 'Outbid', className: 'bg-red-50 text-red-700 ring-red-200' },
  RAISED: { label: () => 'Raised later', className: 'bg-slate-50 text-slate-600 ring-slate-200' },
  LOST: { label: () => 'Not won', className: 'bg-slate-50 text-slate-600 ring-slate-200' },
  CANCELLED: { label: () => 'Cancelled', className: 'bg-slate-50 text-slate-500 ring-slate-200' },
}

const placedAt = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

/** Every bid the signed-in advertiser has placed, newest first. ``refreshKey`` reloads the first page. */
export function BidHistory({ refreshKey = 0 }: { refreshKey?: number }) {
  const [rows, setRows] = useState<BidHistoryRow[] | null>(null)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)

  useEffect(() => {
    let live = true
    dashboardApi
      .myBids(PAGE, 0)
      .then((p) => {
        if (!live) return
        setRows(p.items)
        setTotal(p.total)
        setError(null)
      })
      .catch((e) => live && setError(errorMessage(e, 'Could not load your bids')))
    return () => {
      live = false
    }
  }, [refreshKey])

  const loadMore = useCallback(async () => {
    if (!rows) return
    setLoadingMore(true)
    try {
      const p = await dashboardApi.myBids(PAGE, rows.length)
      setRows([...rows, ...p.items])
      setTotal(p.total)
    } catch (e) {
      setError(errorMessage(e, 'Could not load more bids'))
    } finally {
      setLoadingMore(false)
    }
  }, [rows])

  if (error && !rows) return <p className="text-sm text-red-700">{error}</p>
  if (!rows) return <div className="h-40 animate-pulse rounded-lg bg-slate-50" aria-label="Loading bids" />
  if (rows.length === 0) return <Empty>You haven’t placed any bids yet.</Empty>

  return (
    <div>
      <div className="-mx-4 overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
              <th className="px-4 py-2 font-medium">Placed</th>
              <th className="px-4 py-2 font-medium">Pole</th>
              <th className="px-4 py-2 font-medium">Slot</th>
              <th className="px-4 py-2 font-medium">Round</th>
              <th className="px-4 py-2 text-right font-medium">Amount</th>
              <th className="px-4 py-2 font-medium">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => {
              const o = OUTCOME[r.outcome]
              return (
                <tr key={r.bid_id}>
                  <td className="whitespace-nowrap px-4 py-2 text-slate-600">{placedAt(r.placed_at)}</td>
                  <td className="px-4 py-2 font-medium">
                    <span className="inline-flex items-center gap-1.5">
                      <CategoryDot category={r.category} /> {r.pole_code}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2">
                    {shortDate(r.date)} <span className="text-slate-500">· {r.shift_label}</span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{r.round === 'PREMIUM' ? 'Premium' : 'Qualifying'}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{formatINR(r.amount)}</td>
                  <td className="px-4 py-2">
                    <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${o.className}`}>
                      {o.label(r)}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {rows.length < total && (
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span>
            Showing {rows.length} of {total}
          </span>
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="rounded-md px-3 py-1.5 font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-50"
          >
            {loadingMore ? 'Loading…' : 'Load more'}
          </button>
        </div>
      )}
    </div>
  )
}
