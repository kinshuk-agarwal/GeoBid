import type { AdSeat, SeatStatus } from '@/types'
import { formatINR } from '@/utils/format'

const STATUS: Record<SeatStatus, { label: string; className: string }> = {
  LEADING: { label: 'Top 2', className: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  CONFIRMED: { label: 'Confirmed', className: 'bg-emerald-600 text-white ring-emerald-600' },
  PROVISIONAL: { label: 'Can be taken', className: 'bg-amber-50 text-amber-800 ring-amber-200' },
  PREMIUM: { label: 'Premium', className: 'bg-violet-50 text-violet-800 ring-violet-200' },
  OPEN: { label: 'Open', className: 'bg-slate-50 text-slate-500 ring-slate-200' },
  WON: { label: 'Won', className: 'bg-emerald-600 text-white ring-emerald-600' },
}

/** The slot's rotating ad seats: who holds each and at what bid. */
export function SeatBoard({ seats, myId }: { seats: AdSeat[]; myId: number | null }) {
  return (
    <ol className="divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200">
      {seats.map((s) => {
        const mine = s.advertiser_id !== null && s.advertiser_id === myId
        const st = STATUS[s.status]
        return (
          <li key={s.seat} className={`flex items-center gap-3 px-3 py-2 text-sm ${mine ? 'bg-slate-900 text-white' : ''}`}>
            <span className={`w-12 text-xs ${mine ? 'text-slate-300' : 'text-slate-400'}`}>Seat {s.seat}</span>
            <span className="min-w-0 flex-1 truncate font-medium">
              {s.advertiser_id === null ? <span className="font-normal text-slate-400">Empty</span> : mine ? 'You' : s.alias}
            </span>
            <span className="tabular-nums">{s.amount !== null ? formatINR(s.amount) : ''}</span>
            <span className={`w-24 shrink-0 rounded-full px-2 py-0.5 text-center text-[11px] font-semibold ring-1 ring-inset ${st.className}`}>
              {st.label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
