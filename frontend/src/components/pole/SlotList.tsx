import { ChevronDown, Clock, Gavel } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { formatDuration, useCountdown } from '@/hooks/useCountdown'
import type { Slot } from '@/types'
import { footfallRange, formatINR, formatINRRange } from '@/utils/format'
import { ROUND } from '@/utils/inventory'

const SEAT_TONE: Record<string, string> = {
  LEADING: 'bg-emerald-500',
  CONFIRMED: 'bg-emerald-600',
  PROVISIONAL: 'bg-amber-400',
  PREMIUM: 'bg-violet-500',
  OPEN: 'bg-slate-200',
  WON: 'bg-emerald-600',
}

function SeatDots({ slot }: { slot: Slot }) {
  const seats = slot.auction?.seats ?? []
  if (!seats.length) return null
  return (
    <span className="inline-flex gap-0.5" title={`${seats.filter((s) => s.advertiser_id).length} of ${seats.length} seats taken`}>
      {seats.map((s) => (
        <span key={s.seat} className={`size-1.5 rounded-full ${SEAT_TONE[s.status]}`} />
      ))}
    </span>
  )
}

function Expanded({ slot, onBid, details }: { slot: Slot; onBid: (auctionId: number) => void; details: ReactNode }) {
  const a = slot.auction
  const remaining = useCountdown(a?.status === 'LIVE' ? a.round_ends_at : null)
  const [showDetails, setShowDetails] = useState(false)
  const biddable = a && (a.round === 'QUALIFYING' || a.round === 'PREMIUM')

  return (
    <div className="space-y-3 border-t border-slate-200 bg-slate-50/70 px-3 py-3">
      {a && (
        <div className="grid grid-cols-4 gap-1">
          {a.seats.map((s) => (
            <div key={s.seat} className="rounded-md bg-white px-1.5 py-1 text-center ring-1 ring-slate-200">
              <div className="text-[10px] text-slate-400">Seat {s.seat}</div>
              <div className="text-xs font-semibold tabular-nums">{s.amount !== null ? formatINR(s.amount) : '—'}</div>
              <div className={`mx-auto mt-0.5 h-0.5 w-6 rounded ${SEAT_TONE[s.status]}`} />
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-slate-600">
        <span>
          {a?.next_min_bid != null ? (
            <>
              Min bid <span className="font-semibold text-slate-900">{formatINR(a.next_min_bid)}</span>
            </>
          ) : a?.round === 'BREAK' ? (
            <>Premium from {formatINR(a.premium_floor ?? slot.reserve_price)}</>
          ) : (
            <>Base {formatINR(slot.reserve_price)}</>
          )}
          {slot.expected_price && (
            <span className="text-slate-400"> · usually {formatINRRange(slot.expected_price.low, slot.expected_price.high)}</span>
          )}
        </span>
        {a?.status === 'LIVE' && a.round_ends_at && (
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3" />
            <span className="font-mono">{formatDuration(remaining)}</span>
          </span>
        )}
      </div>

      {a ? (
        <button
          onClick={() => onBid(a.id)}
          className={`inline-flex w-full items-center justify-center gap-2 rounded-lg py-2 text-sm font-semibold ${
            biddable ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50'
          }`}
        >
          <Gavel className="size-4" />
          {biddable ? 'Place bid' : a.status === 'COMPLETED' ? 'View result' : 'View auction'}
        </button>
      ) : (
        <p className="text-center text-xs text-slate-500">No auction for this slot.</p>
      )}

      <button
        onClick={() => setShowDetails((v) => !v)}
        className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800"
      >
        <ChevronDown className={`size-3.5 transition-transform ${showDetails ? 'rotate-180' : ''}`} />
        Price details
      </button>
      {showDetails && details}
    </div>
  )
}

interface Props {
  slots: Slot[]
  selectedId: number | null
  onSelect: (slot: Slot | null) => void
  onBid: (auctionId: number) => void
  renderDetails: (slot: Slot) => ReactNode
}

/** Slots for one day; clicking a row expands it in place with a Place bid button. */
export function SlotList({ slots, selectedId, onSelect, onBid, renderDetails }: Props) {
  return (
    <div className="divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200">
      {slots.map((slot) => {
        const open = slot.id === selectedId
        const a = slot.auction
        const round = a?.status === 'LIVE' && a.round && a.round !== 'CLOSED' ? ROUND[a.round] : null
        return (
          <div key={slot.id}>
            <button
              onClick={() => onSelect(open ? null : slot)}
              aria-expanded={open}
              className={`grid w-full grid-cols-[1fr_auto] items-center gap-x-3 px-3 py-2 text-left ${
                open ? 'bg-slate-900 text-white' : 'hover:bg-slate-50'
              }`}
            >
              <span className="min-w-0">
                <span className="block text-sm font-semibold tabular-nums">{slot.shift_label}</span>
                <span className={`flex items-center gap-1.5 text-[11px] ${open ? 'text-slate-300' : 'text-slate-500'}`}>
                  {slot.slot_footfall !== null && <span className="tabular-nums">{footfallRange(slot.slot_footfall)}</span>}
                  {round && (
                    <>
                      <span aria-hidden>·</span>
                      <span>{round.label}</span>
                    </>
                  )}
                  <SeatDots slot={slot} />
                </span>
              </span>
              <span className="text-right">
                <span className="block text-sm font-semibold tabular-nums">
                  {formatINR(a?.next_min_bid ?? slot.reserve_price)}
                </span>
                <span className="block text-[11px] text-slate-400">
                  {a?.next_min_bid != null ? 'min bid' : 'base'}
                </span>
              </span>
            </button>
            {open && <Expanded slot={slot} onBid={onBid} details={renderDetails(slot)} />}
          </div>
        )
      })}
    </div>
  )
}
