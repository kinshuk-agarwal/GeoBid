import { CheckCircle2, Gavel, PauseCircle, Trophy } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router'

import { auctionsApi } from '@/api'
import { errorMessage } from '@/api/client'
import type { Auction, Bid, User } from '@/types'
import { formatINR } from '@/utils/format'
import { formatWhen } from '@/utils/inventory'

import { Spinner } from '../common/Spinner'

interface Props {
  auction: Auction
  user: User | null
  /** the current round's deadline has passed; waiting for the server to move on */
  roundOver: boolean
  onPlaced: (auction: Auction, bid: Bid) => void
}

function Note({ tone = 'slate', children }: { tone?: 'slate' | 'emerald' | 'amber'; children: React.ReactNode }) {
  const tones = {
    slate: 'border-slate-200 bg-slate-50 text-slate-700',
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    amber: 'border-amber-200 bg-amber-50 text-amber-900',
  }
  return <div className={`rounded-lg border px-3 py-2.5 text-sm ${tones[tone]}`}>{children}</div>
}

export function BidBox({ auction, user, roundOver, onPlaced }: Props) {
  const location = useLocation()
  const viewer = auction.viewer
  const minimum = viewer?.next_min_bid ?? auction.next_min_bid
  const [amount, setAmount] = useState<string>(minimum ? String(minimum) : '')
  const [touched, setTouched] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Follow the minimum until the user types their own amount.
  useEffect(() => {
    if (minimum && (!touched || Number(amount) < minimum)) setAmount(String(minimum))
  }, [minimum]) // react only to a new minimum, not to typing

  // A success message goes stale once the user loses their seat.
  useEffect(() => {
    if (!viewer?.seat) setSuccess(null)
  }, [viewer?.seat])

  if (auction.status === 'COMPLETED' || auction.status === 'CANCELLED') {
    const mine = auction.winners.find((w) => w.advertiser_id === user?.id)
    return mine ? (
      <Note tone="emerald">
        <div className="flex items-center gap-2 font-semibold">
          <Trophy className="size-4" /> You won seat {mine.seat} at {formatINR(mine.amount)}
        </div>
        <p className="mt-1 text-xs">Your ad rotates equally with the other {auction.winners.length - 1} seat holders.</p>
      </Note>
    ) : (
      <Note>
        {auction.winners.length
          ? `Auction closed: ${auction.winners.length} of ${auction.seats_total} seats booked.`
          : 'Auction closed with no bids; the slot went unsold.'}
      </Note>
    )
  }

  if (auction.round === 'BREAK') {
    return (
      <Note tone="amber">
        <div className="flex items-center gap-2 font-semibold">
          <PauseCircle className="size-4" /> Break until {formatWhen(auction.premium_start_time)}
        </div>
        <p className="mt-1 text-xs">
          Seats 1–2 are confirmed. From 16:00 anyone can take seat 4, then seat 3, with a bid from{' '}
          <span className="font-semibold">{formatINR(auction.premium_floor ?? auction.reserve_price)}</span>.
        </p>
      </Note>
    )
  }

  if (auction.round === null || auction.round === 'CLOSED') {
    return <Note>Bidding isn’t open right now.</Note>
  }

  if (!user) {
    return (
      <Note>
        <Link to="/login" state={{ from: location.pathname + location.search }} className="font-semibold underline underline-offset-2">
          Sign in
        </Link>{' '}
        with an advertiser account to bid.
      </Note>
    )
  }

  const canBid = !!viewer?.can_bid && !roundOver && minimum !== null
  const value = Number(amount)
  const tooLow = amount !== '' && minimum !== null && value < minimum

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!canBid) return
    setSubmitting(true)
    setError(null)
    setSuccess(null)
    try {
      // The server re-validates everything; this check only saves a round trip.
      const res = await auctionsApi.placeBid(auction.id, value)
      onPlaced(res.auction, res.bid)
      setTouched(false)
      const seat = res.auction.viewer?.seat
      setSuccess(seat ? `Bid placed. You hold seat ${seat}.` : 'Bid placed.')
    } catch (err) {
      setError(errorMessage(err, 'Bid was not accepted'))
    } finally {
      setSubmitting(false)
    }
  }

  const premium = auction.round === 'PREMIUM'
  const status =
    viewer?.seat_status === 'CONFIRMED'
      ? 'Your seat is confirmed.'
      : viewer?.seat
        ? `You hold seat ${viewer.seat}${viewer.seat_status === 'LEADING' ? '' : ' (it can be taken)'}. Raise your bid to move up.`
        : null

  return (
    <form onSubmit={submit} className="space-y-2">
      {status && <p className="text-xs font-medium text-slate-700">{status}</p>}
      {!canBid && viewer?.reason && <Note>{viewer.reason}</Note>}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">₹</span>
          <input
            aria-label="Bid amount"
            inputMode="numeric"
            value={amount}
            onChange={(e) => {
              setTouched(true)
              setSuccess(null)
              setAmount(e.target.value.replace(/[^\d]/g, ''))
            }}
            disabled={!canBid || submitting}
            className={`w-full rounded-lg border py-2 pl-7 pr-3 text-lg font-semibold tabular-nums focus:outline-none focus:ring-2 disabled:bg-slate-50 disabled:text-slate-400 ${
              tooLow ? 'border-red-300 focus:ring-red-100' : 'border-slate-200 focus:border-slate-400 focus:ring-slate-200'
            }`}
          />
        </div>
        <button
          type="submit"
          disabled={!canBid || submitting || tooLow || amount === ''}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {submitting ? <Spinner className="size-4 border-slate-500 border-t-white" /> : <Gavel className="size-4" />}
          Place bid
        </button>
      </div>
      {minimum !== null && (
        <div className="flex items-center justify-between gap-2 text-xs text-slate-500">
          <span className={tooLow ? 'text-red-700' : ''}>
            Min {formatINR(minimum)}
            {premium && auction.premium_floor ? ` · premium from ${formatINR(auction.premium_floor)}` : ''}
          </span>
          <span className="flex gap-1">
            {[5, 10].map((k) => (
              <button
                key={k}
                type="button"
                disabled={!canBid}
                onClick={() => {
                  setTouched(true)
                  setAmount(String(minimum + k * auction.min_increment))
                }}
                className="rounded border border-slate-200 px-1.5 py-0.5 tabular-nums hover:bg-slate-50 disabled:opacity-50"
              >
                +{formatINR(k * auction.min_increment)}
              </button>
            ))}
          </span>
        </div>
      )}
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-800">{error}</p>}
      {success && (
        <p className="flex items-center gap-1.5 rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          <CheckCircle2 className="size-3.5" /> {success}
        </p>
      )}
    </form>
  )
}
