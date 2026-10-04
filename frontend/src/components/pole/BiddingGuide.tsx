import { Calculator, Crown, Gavel, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { configApi } from '@/api'
import type { TariffConfig } from '@/types'
import { formatINR } from '@/utils/format'

const STEPS: { title: string; body: string }[] = [
  {
    title: 'Find a pole',
    body: 'Red markers have the highest footfall. Compare footfall, visibility score and rank in this panel.',
  },
  {
    title: 'Pick a 2-hour slot',
    body: 'Every pole has twelve 2-hour slots per day. Each slot has its own base price, set by the footfall expected in it.',
  },
  {
    title: 'Qualifying round: bid for one of 4 seats',
    body: 'Each slot is a rolling ad shared by 4 advertisers. Until 12:00 the day before, the top 4 bidders hold the seats.',
  },
  {
    title: 'Top 2 are confirmed at 12:00',
    body: 'Seats 1 and 2 are locked in. Seats 3 and 4 are held but can still be taken.',
  },
  {
    title: 'Premium round: take a seat',
    body: 'From 16:00 the day before, anyone else can bid at the premium price to take seat 4, then seat 3. At the close every seat holder pays their own bid and the ad rotates equally.',
  },
]

const n = (x: number) => String(+x.toFixed(2))

function Formula({ children }: { children: React.ReactNode }) {
  return <div className="rounded-md bg-slate-50 px-2.5 py-1.5 font-mono text-[11px] leading-relaxed text-slate-800">{children}</div>
}

/** Exact pricing formulas, with the live numbers from /tariff/config. */
function Formulas({ c }: { c: TariffConfig }) {
  const span = c.pole_multiplier_max - c.pole_multiplier_min
  const a = c.auction
  // Worked example: pole value 80, a slot 1.5× busier than the pole's average slot.
  const exPoleMult = c.pole_multiplier_min + (span * 80) / 100
  const exSlotMult = Math.min(Math.max(1.5 ** c.slot_footfall_exponent, c.slot_multiplier_min), c.slot_multiplier_max)
  const exRaw = c.base_rate * exPoleMult * exSlotMult
  const exBase = Math.round(exRaw / c.rounding) * c.rounding
  const exTop = exBase + 1200
  const exFloor = Math.ceil((exTop * a.premium_floor_multiplier) / c.rounding) * c.rounding

  return (
    <div className="space-y-3">
      <section className="space-y-1.5 rounded-lg border border-slate-200 p-3">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold">
          <Calculator className="size-4 text-slate-500" /> Base price (qualifying round)
        </h3>
        <Formula>
          base price = {formatINR(c.base_rate)} × pole multiplier × slot multiplier
          <br />
          <span className="text-slate-500">rounded to the nearest {formatINR(c.rounding)}</span>
        </Formula>
        <Formula>
          pole value = {n(c.footfall_weight)} × footfall score + {n(c.visibility_weight)} × visibility score
          <br />
          pole multiplier = {n(c.pole_multiplier_min)} + {n(span)} × pole value ÷ 100
          <span className="text-slate-500"> ({n(c.pole_multiplier_min)}–{n(c.pole_multiplier_max)})</span>
        </Formula>
        <Formula>
          avg slot footfall = daily footfall × 2 ÷ 24
          <br />
          slot multiplier = (slot footfall ÷ avg slot footfall)<sup>{n(c.slot_footfall_exponent)}</sup>
          <span className="text-slate-500">, kept between {n(c.slot_multiplier_min)} and {n(c.slot_multiplier_max)}</span>
        </Formula>
        <p className="text-[11px] leading-relaxed text-slate-600">
          <span className="font-medium text-slate-800">Example:</span> pole value 80 → ×{n(exPoleMult)}; a slot 1.5× busier than
          average → ×{exSlotMult.toFixed(3)}; {formatINR(c.base_rate)} × {n(exPoleMult)} × {exSlotMult.toFixed(3)} = {formatINR(Math.round(exRaw))} →{' '}
          <span className="font-medium text-slate-800">{formatINR(exBase)}</span>.
        </p>
        <ul className="list-disc space-y-0.5 pl-4 text-[11px] leading-relaxed text-slate-600">
          <li>While fewer than {a.seats_per_slot} have bid, the minimum bid is the base price.</li>
          <li>Once all {a.seats_per_slot} seats are held: minimum = lowest seat bid + {formatINR(a.min_increment)}.</li>
          <li>Raising your own bid: your bid + {formatINR(a.min_increment)}.</li>
          <li>No matching bids: a bid can’t be within {formatINR(a.min_increment)} of another seat holder’s bid.</li>
          <li>At {a.qualifying_close_time} the day before, the top {a.confirmed_seats} are confirmed.</li>
        </ul>
      </section>

      <section className="space-y-1.5 rounded-lg border border-slate-200 p-3">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold">
          <Crown className="size-4 text-slate-500" /> Premium round
        </h3>
        <Formula>
          premium price = {n(a.premium_floor_multiplier)} × top qualifying bid
          <br />
          <span className="text-slate-500">rounded up to the next {formatINR(c.rounding)}</span>
        </Formula>
        <ul className="list-disc space-y-0.5 pl-4 text-[11px] leading-relaxed text-slate-600">
          <li>
            Open from {a.premium_round_start_time} the day before until {a.premium_close_before_slot_minutes / 60} hours before the slot.
          </li>
          <li>Anyone except the {a.confirmed_seats} confirmed bidders can bid.</li>
          <li>If seat 3 or 4 is empty or still held by a qualifying bid, the minimum bid is the premium price.</li>
          <li>Once both are held by premium bids: minimum = lower premium seat bid + {formatINR(a.min_increment)}.</li>
          <li>A new premium bid takes seat 4, then seat 3; the lowest holder is bumped and can bid again.</li>
        </ul>
        <p className="text-[11px] leading-relaxed text-slate-600">
          <span className="font-medium text-slate-800">Example:</span> top qualifying bid {formatINR(exTop)} → {n(a.premium_floor_multiplier)} ×{' '}
          {formatINR(exTop)} = {formatINR(exTop * a.premium_floor_multiplier)} → premium price{' '}
          <span className="font-medium text-slate-800">{formatINR(exFloor)}</span>.
        </p>
      </section>
    </div>
  )
}

export function BiddingGuide({ showHint = true }: { showHint?: boolean }) {
  // undefined = loading, null = unavailable (the steps above still explain the rules)
  const [config, setConfig] = useState<TariffConfig | null | undefined>(undefined)
  useEffect(() => {
    configApi.tariff().then(setConfig).catch(() => setConfig(null))
  }, [])

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <Gavel className="size-4 text-slate-500" />
          <h2 className="text-base font-semibold tracking-tight">How bidding works</h2>
        </div>
        {showHint && <p className="mt-1 text-sm text-slate-500">Select a pole on the map to see its slots and prices.</p>}
      </div>
      <ol className="space-y-3">
        {STEPS.map((s, i) => (
          <li key={s.title} className="grid grid-cols-[1.5rem_1fr] gap-x-2.5">
            <span className="flex size-6 items-center justify-center rounded-full bg-slate-900 text-[11px] font-semibold text-white">
              {i + 1}
            </span>
            <div>
              <div className="text-sm font-medium">{s.title}</div>
              <p className="mt-0.5 text-xs leading-relaxed text-slate-600">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
      {config ? <Formulas c={config} /> : config === undefined && <div className="h-40 animate-pulse rounded-lg bg-slate-50" aria-label="Loading formulas" />}
    </div>
  )
}

/** The guide in a popup, so it can be read without closing the selected pole. */
export function BiddingGuideModal({ onClose }: { onClose: () => void }) {
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
        aria-label="How bidding works"
        onClick={(e) => e.stopPropagation()}
        className="relative max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:max-w-lg sm:rounded-2xl"
      >
        <button onClick={onClose} aria-label="Close guide" className="absolute right-3 top-3 rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
          <X className="size-4" />
        </button>
        <BiddingGuide showHint={false} />
      </div>
    </div>
  )
}

