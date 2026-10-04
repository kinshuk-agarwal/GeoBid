import { useCountdown, formatDuration } from '@/hooks/useCountdown'
import type { AuctionRow } from '@/types'
import { footfallRange, formatINR } from '@/utils/format'
import { ROUND } from '@/utils/inventory'

import { CategoryDot } from '../common/CategoryBadge'

export function shortDate(iso: string) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
}

export function RoundPill({ row }: { row: AuctionRow }) {
  if (row.status === 'COMPLETED') return <span className="text-xs text-slate-500">Closed</span>
  if (!row.round || row.round === 'CLOSED') return <span className="text-xs text-slate-500">—</span>
  const r = ROUND[row.round]
  return <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${r.className}`}>{r.label}</span>
}

export function EndsIn({ iso }: { iso: string | null }) {
  const ms = useCountdown(iso)
  return <span className="font-mono text-xs tabular-nums text-slate-600">{iso ? formatDuration(ms) : '—'}</span>
}

export function SeatsFilled({ row }: { row: AuctionRow }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs tabular-nums text-slate-600" title={`${row.seats_filled} of ${row.seats_total} seats`}>
      {Array.from({ length: row.seats_total }, (_, i) => (
        <span key={i} className={`size-1.5 rounded-full ${i < row.seats_filled ? 'bg-slate-700' : 'bg-slate-200'}`} />
      ))}
    </span>
  )
}

export interface Column {
  key: string
  label: string
  align?: 'right'
  render: (row: AuctionRow) => React.ReactNode
}

export const COLUMNS: Record<string, Column> = {
  pole: {
    key: 'pole',
    label: 'Pole',
    render: (r) => (
      <span className="inline-flex items-center gap-1.5 font-medium">
        <CategoryDot category={r.category} /> {r.pole_code}
      </span>
    ),
  },
  slot: {
    key: 'slot',
    label: 'Slot',
    render: (r) => (
      <span className="whitespace-nowrap">
        {shortDate(r.date)} <span className="text-slate-500">· {r.shift_label}</span>
      </span>
    ),
  },
  footfall: { key: 'footfall', label: 'Footfall', render: (r) => (r.slot_footfall !== null ? footfallRange(r.slot_footfall) : '—') },
  round: { key: 'round', label: 'Round', render: (r) => <RoundPill row={r} /> },
  seats: { key: 'seats', label: 'Seats', render: (r) => <SeatsFilled row={r} /> },
  top: { key: 'top', label: 'Top bid', align: 'right', render: (r) => (r.top_bid !== null ? formatINR(r.top_bid) : '—') },
  min: { key: 'min', label: 'Min bid', align: 'right', render: (r) => (r.next_min_bid !== null ? formatINR(r.next_min_bid) : '—') },
  bids: { key: 'bids', label: 'Bids', align: 'right', render: (r) => r.bid_count },
  ends: { key: 'ends', label: 'Round ends in', render: (r) => (r.status === 'LIVE' ? <EndsIn iso={r.round_ends_at} /> : '—') },
  revenue: { key: 'revenue', label: 'Revenue', align: 'right', render: (r) => formatINR(r.revenue) },
}

/** A compact, horizontally scrollable table of auctions. */
export function AuctionTable({
  rows,
  columns,
  actions,
  empty = 'Nothing here yet.',
}: {
  rows: AuctionRow[]
  columns: Column[]
  actions?: (row: AuctionRow) => React.ReactNode
  empty?: string
}) {
  if (!rows.length) return <p className="py-6 text-center text-sm text-slate-500">{empty}</p>
  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
            {columns.map((c) => (
              <th key={c.key} className={`px-4 py-2 font-medium ${c.align === 'right' ? 'text-right' : ''}`}>
                {c.label}
              </th>
            ))}
            {actions && <th className="px-4 py-2" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50">
              {columns.map((c) => (
                <td key={c.key} className={`px-4 py-2 tabular-nums ${c.align === 'right' ? 'text-right' : ''}`}>
                  {c.render(r)}
                </td>
              ))}
              {actions && <td className="whitespace-nowrap px-4 py-2 text-right">{actions(r)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
