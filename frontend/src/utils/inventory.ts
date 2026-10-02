import type { AuctionRound, Demand, MarketStatus, SlotStatus } from '@/types'

export const DEMAND: Record<Demand, { label: string; className: string; bars: number }> = {
  LOW: { label: 'Low', className: 'bg-slate-100 text-slate-600', bars: 1 },
  LOW_MEDIUM: { label: 'Low–Med', className: 'bg-slate-100 text-slate-700', bars: 2 },
  MEDIUM: { label: 'Medium', className: 'bg-sky-50 text-sky-800', bars: 3 },
  HIGH: { label: 'High', className: 'bg-indigo-50 text-indigo-800', bars: 4 },
  VERY_HIGH: { label: 'Very high', className: 'bg-violet-100 text-violet-900', bars: 5 },
}

export const SLOT_STATUS: Record<SlotStatus, { label: string; className: string }> = {
  AVAILABLE: { label: 'No auction yet', className: 'text-slate-500' },
  IN_AUCTION: { label: 'In auction', className: 'text-amber-700' },
  SOLD: { label: 'Sold', className: 'text-slate-500' },
  UNSOLD: { label: 'Unsold', className: 'text-slate-500' },
}

export const MARKET_STATUS: Record<MarketStatus, { label: string; className: string }> = {
  AVAILABLE: { label: 'Inventory available', className: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  AUCTIONING: { label: 'Auctioning', className: 'bg-amber-50 text-amber-800 ring-amber-200' },
  SOLD_OUT: { label: 'Sold out', className: 'bg-slate-100 text-slate-700 ring-slate-200' },
  NO_INVENTORY: { label: 'No inventory', className: 'bg-slate-100 text-slate-600 ring-slate-200' },
}

/** "Tomorrow · Sat, 3 Oct" from a YYYY-MM-DD local date. */
export function formatAdDate(isoDate: string, isTomorrow: boolean): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  const label = new Date(y, m - 1, d).toLocaleDateString('en-IN', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
  return isTomorrow ? `Tomorrow · ${label}` : label
}

export const ROUND: Record<AuctionRound, { label: string; hint: string; className: string }> = {
  QUALIFYING: {
    label: 'Qualifying round',
    hint: 'Anyone can bid until 12:00 the day before; the top 4 hold seats.',
    className: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  },
  BREAK: {
    label: 'Break',
    hint: 'No bidding until 16:00. Seats 1–2 are confirmed.',
    className: 'bg-amber-50 text-amber-800 ring-amber-200',
  },
  PREMIUM: {
    label: 'Premium round',
    hint: 'Anyone can bid from 1.5× the top bid to take seat 4, then seat 3.',
    className: 'bg-violet-50 text-violet-800 ring-violet-200',
  },
  CLOSED: { label: 'Closed', hint: 'Bidding has ended.', className: 'bg-slate-100 text-slate-700 ring-slate-200' },
}

/** "16:00, Sat 3 Oct" in the viewer's locale. */
export function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}
