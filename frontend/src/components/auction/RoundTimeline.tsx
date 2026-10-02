import { Check } from 'lucide-react'

import type { Auction, AuctionRound } from '@/types'
import { formatWhen } from '@/utils/inventory'

const STEPS: { round: AuctionRound; title: string; who: string; from: keyof Auction; to: keyof Auction }[] = [
  { round: 'QUALIFYING', title: 'Qualifying round', who: 'Anyone · top 4 hold seats', from: 'start_time', to: 'qualifying_end_time' },
  { round: 'BREAK', title: 'Break', who: 'Seats 1–2 confirmed · no bidding', from: 'qualifying_end_time', to: 'premium_start_time' },
  { round: 'PREMIUM', title: 'Premium round', who: 'Anyone · takes seat 4, then 3', from: 'premium_start_time', to: 'end_time' },
]
const ORDER: (AuctionRound | null)[] = [null, 'QUALIFYING', 'BREAK', 'PREMIUM', 'CLOSED']

/** Qualifying round → break → premium round, with the current step highlighted. */
export function RoundTimeline({ auction }: { auction: Auction }) {
  const current = ORDER.indexOf(auction.round)
  return (
    <ol className="grid gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-3">
      {STEPS.map((s) => {
        const idx = ORDER.indexOf(s.round)
        const state = idx < current ? 'done' : idx === current ? 'now' : 'next'
        return (
          <li
            key={s.round}
            className={`px-4 py-3 ${state === 'now' ? 'bg-slate-900 text-white' : 'bg-white'}`}
            aria-current={state === 'now' ? 'step' : undefined}
          >
            <div className="flex items-center gap-2 text-sm font-semibold">
              <span
                className={`flex size-5 items-center justify-center rounded-full text-[11px] ${
                  state === 'done'
                    ? 'bg-emerald-600 text-white'
                    : state === 'now'
                      ? 'bg-white text-slate-900'
                      : 'bg-slate-100 text-slate-500'
                }`}
              >
                {state === 'done' ? <Check className="size-3" /> : idx}
              </span>
              {s.title}
              {state === 'now' && (
                <span className="ml-auto rounded bg-white/15 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide">
                  Now
                </span>
              )}
            </div>
            <div className={`mt-1 text-xs ${state === 'now' ? 'text-slate-300' : 'text-slate-500'}`}>{s.who}</div>
            <div className={`mt-0.5 text-xs tabular-nums ${state === 'now' ? 'text-slate-200' : 'text-slate-600'}`}>
              {formatWhen(auction[s.from] as string)} → {formatWhen(auction[s.to] as string)}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
