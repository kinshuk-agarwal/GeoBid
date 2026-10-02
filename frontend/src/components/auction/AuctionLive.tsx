import { Clock, Eye } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { useAuction } from '@/hooks/useAuction'
import { useAuctionNotifications } from '@/hooks/useAuctionNotifications'
import type { SocketStatus } from '@/hooks/useAuctionSocket'
import { useAuth } from '@/hooks/useAuth'
import { formatDuration, useCountdown } from '@/hooks/useCountdown'
import type { Auction } from '@/types'
import { formatINR, formatINRRange, footfallRange } from '@/utils/format'
import { ROUND, formatAdDate } from '@/utils/inventory'

import { CategoryBadge } from '../common/CategoryBadge'
import { Spinner } from '../common/Spinner'
import { BidBox } from './BidBox'
import { RoundTimeline } from './RoundTimeline'
import { SeatBoard } from './SeatBoard'

const CLOCK_LABEL: Record<string, string> = {
  QUALIFYING: 'Qualifying ends in',
  BREAK: 'Premium opens in',
  PREMIUM: 'Premium ends in',
}

function LiveDot({ status, viewers }: { status: SocketStatus; viewers: number | null }) {
  const live = status === 'open'
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs ${live ? 'text-emerald-700' : 'text-amber-700'}`}>
      <span className={`size-1.5 rounded-full ${live ? 'animate-pulse bg-emerald-500' : 'bg-amber-500'}`} />
      {live ? 'Live' : 'Reconnecting…'}
      {live && viewers !== null && (
        <span className="inline-flex items-center gap-1 text-slate-500">
          <Eye className="size-3" /> {viewers}
        </span>
      )}
    </span>
  )
}

function isTomorrow(iso: string) {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toLocaleDateString('en-CA') === iso
}

/** Live auction: round, countdown, seats, bid box and recent bids.
 * Used inside the bid popup and on the full auction page. */
export function AuctionLive({ auctionId, full = false }: { auctionId: string; full?: boolean }) {
  const { user } = useAuth()
  const onEvent = useAuctionNotifications(user)
  const { auction, bids, error, clockOffset, refresh, applyBidResult, socket, viewers } = useAuction(auctionId, onEvent)

  const open = auction?.status === 'LIVE' || auction?.status === 'SCHEDULED'
  const remaining = useCountdown(open ? auction?.round_ends_at : null, clockOffset)
  const roundOver = open && !!auction?.round_ends_at && remaining === 0

  // When a round's clock runs out, fetch the next state from the server.
  const pending = useRef(false)
  useEffect(() => {
    if (!roundOver || pending.current) return
    pending.current = true
    const t = setTimeout(() => void refresh().finally(() => (pending.current = false)), 1500)
    return () => clearTimeout(t)
  }, [roundOver, refresh])

  if (error && !auction) return <p className="p-4 text-sm text-red-700">{error}</p>
  if (!auction) {
    return (
      <div className="flex justify-center p-10">
        <Spinner className="size-6" />
      </div>
    )
  }

  const round = auction.round && auction.round !== 'CLOSED' ? ROUND[auction.round] : null
  return (
    <div className="space-y-4">
      <Header auction={auction} socket={socket} viewers={viewers} />

      {full && <RoundTimeline auction={auction} />}

      <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
        {round ? (
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${round.className}`}>
            {round.label}
          </span>
        ) : (
          <span className="text-xs font-medium text-slate-600">{auction.status === 'COMPLETED' ? 'Closed' : 'Not open'}</span>
        )}
        {open && auction.round && CLOCK_LABEL[auction.round] && (
          <span className="flex items-center gap-1.5 text-xs text-slate-600">
            <Clock className="size-3.5" /> {CLOCK_LABEL[auction.round]}
            <span className="font-mono font-semibold text-slate-900">{formatDuration(remaining)}</span>
          </span>
        )}
      </div>

      <SeatBoard seats={auction.seats} myId={user?.id ?? null} />
      <p className="-mt-2 text-[11px] text-slate-500">
        {auction.seats_total} ads rotate equally; each seat pays its own bid. Base {formatINR(auction.reserve_price)}
        {auction.expected_price &&
          ` · usually ${formatINRRange(auction.expected_price.low, auction.expected_price.high)} on a ${auction.expected_price.weekday}`}
        .
      </p>

      <BidBox key={auction.id} auction={auction} user={user} roundOver={roundOver} onPlaced={applyBidResult} />

      {bids.length > 0 && (
        <div>
          <div className="mb-1 text-xs font-medium text-slate-500">Recent bids</div>
          <ul className="space-y-0.5 text-xs">
            {(full ? bids : bids.slice(0, 5)).map((b) => (
              <li key={b.id} className="flex justify-between">
                <span className="text-slate-600">
                  {b.advertiser_id === user?.id ? <span className="font-semibold text-slate-900">You</span> : b.bidder_alias}
                  {b.round === 'PREMIUM' && <span className="ml-1 text-violet-700">· premium</span>}
                </span>
                <span className="font-medium tabular-nums">{formatINR(b.amount)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Header({ auction, socket, viewers }: { auction: Auction; socket: SocketStatus; viewers: number | null }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold tracking-tight">{auction.pole.code}</span>
          <CategoryBadge category={auction.pole.category} />
        </div>
        <p className="text-sm text-slate-600">
          {formatAdDate(auction.date, isTomorrow(auction.date))} · {auction.shift_label}
          {auction.slot_footfall !== null && (
            <span className="text-slate-400"> · {footfallRange(auction.slot_footfall)} footfall</span>
          )}
        </p>
      </div>
      <LiveDot status={socket} viewers={viewers} />
    </div>
  )
}
