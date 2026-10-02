import { Gavel } from 'lucide-react'

const STEPS: { title: string; body: string }[] = [
  {
    title: 'Find a pole',
    body: 'Red markers have the highest footfall. Compare footfall, visibility score and rank in this panel.',
  },
  {
    title: 'Pick a shift',
    body: 'Every pole has twelve 2-hour shifts per day. Evening (16:00–20:00) has the highest demand.',
  },
  {
    title: 'Check the base price and expected range',
    body: 'Each shift has a base price (the reserve): the pole’s footfall and visibility scores × the footfall expected in that 2-hour slot on that day. Bidding starts there. The expected range shows what this shift has typically sold for on that weekday.',
  },
  {
    title: 'Bid for one of 4 seats',
    body: 'Each slot is a rolling ad shared by 4 advertisers. Until 12:00 the day before, the top 4 bidders hold the seats. Bids must be ₹100 apart; no matching bids.',
  },
  {
    title: 'Top 2 are confirmed at 12:00',
    body: 'Seats 1 and 2 are locked in. Seats 3 and 4 are held but can still be taken.',
  },
  {
    title: 'Premium round: take a seat',
    body: 'From 16:00 until 2 hours before the slot, anyone can bid from 1.5× the top bid. Each premium bid takes seat 4, then seat 3. At the close every seat holder pays their own bid.',
  },
]

export function BiddingGuide({ compact = false }: { compact?: boolean }) {
  const list = (
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
  )

  const note = (
    <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600">
      <span className="font-medium text-slate-900">Base price ≠ final price.</span> Advertisers bid above the base
      price; the highest bid when the auction closes is the final price.
    </p>
  )

  if (compact) {
    return (
      <details className="group rounded-xl border border-slate-200 bg-white">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium [&::-webkit-details-marker]:hidden">
          <Gavel className="size-4 text-slate-500" />
          How to bid
          <span className="ml-auto text-xs text-slate-400 group-open:hidden">Show</span>
          <span className="ml-auto hidden text-xs text-slate-400 group-open:inline">Hide</span>
        </summary>
        <div className="space-y-4 border-t border-slate-100 px-4 py-4">
          {list}
          {note}
        </div>
      </details>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <Gavel className="size-4 text-slate-500" />
          <h2 className="text-base font-semibold tracking-tight">How bidding works</h2>
        </div>
        <p className="mt-1 text-sm text-slate-500">Select a pole on the map to see its shifts and prices.</p>
      </div>
      {list}
      {note}
    </div>
  )
}
