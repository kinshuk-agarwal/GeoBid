import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { AdvertiserDashboardData } from '@/types'
import { formatINR, formatNumber } from '@/utils/format'

import { shortDate } from './AuctionTable'

type WonSeat = AdvertiserDashboardData['won'][number]
type SortKey = 'slot' | 'predicted'
type Sort = { key: SortKey; dir: 'asc' | 'desc' }

// Outside the predicted range: one arrowhead, green up or red down. Inside it:
// green over red, with the side the count leaned to (vs the forecast figure)
// lit and the other faded.
const GREEN = '#15803d'
const RED = '#dc2626'
const FADED = 0.2
type Trend = 'up' | 'down' | 'within-up' | 'within-down'
const LABEL: Record<Trend, string> = {
  up: 'Above the forecast range',
  down: 'Below the forecast range',
  'within-up': 'Within the forecast range, slightly above the forecast',
  'within-down': 'Within the forecast range, slightly below the forecast',
}

/** Arrowhead (the reference shape), pointing up or down. */
function Arrowhead({ dir, color, opacity = 1, size }: { dir: 'up' | 'down'; color: string; opacity?: number; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden style={dir === 'down' ? { transform: 'rotate(180deg)' } : undefined}>
      <polygon points="50,0 100,100 50,78 0,100" fill={color} fillOpacity={opacity} />
    </svg>
  )
}

function TrendMark({ trend }: { trend: Trend }) {
  if (trend === 'up') return <Arrowhead dir="up" color={GREEN} size={12} />
  if (trend === 'down') return <Arrowhead dir="down" color={RED} size={12} />
  return (
    <span className="inline-flex flex-col items-center gap-px">
      <Arrowhead dir="up" color={GREEN} size={8} opacity={trend === 'within-up' ? 1 : FADED} />
      <Arrowhead dir="down" color={RED} size={8} opacity={trend === 'within-down' ? 1 : FADED} />
    </span>
  )
}

/** Measured count vs the forecast; the exact % difference is in the tooltip. */
function Versus({ actual, predicted, low, high }: { actual: number; predicted: number | null; low: number | null; high: number | null }) {
  if (predicted === null || low === null || high === null || predicted <= 0) return null
  const trend: Trend = actual > high ? 'up' : actual < low ? 'down' : actual >= predicted ? 'within-up' : 'within-down'
  const change = ((actual - predicted) / predicted) * 100
  return (
    <span title={`${LABEL[trend]}: ${change >= 0 ? '+' : '−'}${Math.abs(change).toFixed(1)}% vs the forecast of ${formatNumber(predicted)}`} className="inline-flex w-3 justify-center">
      <TrendMark trend={trend} />
      <span className="sr-only">{LABEL[trend].toLowerCase()}</span>
    </span>
  )
}

const slotKey = (w: WonSeat) => `${w.date} ${w.shift_label.slice(0, 5)}`

function SortHeader({ label, k, sort, onSort, align = 'left' }: { label: string; k: SortKey; sort: Sort; onSort: (k: SortKey) => void; align?: 'left' | 'right' }) {
  const active = sort.key === k
  const Icon = !active ? ArrowUpDown : sort.dir === 'asc' ? ArrowUp : ArrowDown
  return (
    <th className={`px-4 py-2 font-medium ${align === 'right' ? 'text-right' : ''}`} aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button
        onClick={() => onSort(k)}
        className={`inline-flex items-center gap-1 rounded hover:text-slate-900 ${active ? 'text-slate-900' : ''}`}
        title={`Sort by ${label.toLowerCase()}`}
      >
        {label}
        <Icon className={`size-3.5 ${active ? '' : 'text-slate-300'}`} />
      </button>
    </th>
  )
}

/** Seats won, with predicted vs measured footfall; sortable by slot or forecast. */
export function SeatsWon({ rows }: { rows: WonSeat[] }) {
  const [sort, setSort] = useState<Sort>({ key: 'slot', dir: 'desc' })
  const onSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }))

  const sorted = useMemo(() => {
    const out = [...rows]
    const sign = sort.dir === 'asc' ? 1 : -1
    out.sort((a, b) => {
      if (sort.key === 'predicted') {
        const pa = a.predicted_footfall ?? -1
        const pb = b.predicted_footfall ?? -1
        if (pa !== pb) return (pa - pb) * sign
      }
      return slotKey(a).localeCompare(slotKey(b)) * (sort.key === 'slot' ? sign : -1)
    })
    return out
  }, [rows, sort])

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
        <span className="inline-flex items-center gap-1">
          <TrendMark trend="up" /> Above forecast
        </span>
        <span className="inline-flex items-center gap-1">
          <TrendMark trend="down" /> Below forecast
        </span>
        <span className="inline-flex items-center gap-1">
          <TrendMark trend="within-up" />
          <TrendMark trend="within-down" /> Within forecast (lit side = which way it leaned)
        </span>
      </div>
      <div className="-mx-4 overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
              <th className="px-4 py-2 font-medium">Pole</th>
              <SortHeader label="Slot" k="slot" sort={sort} onSort={onSort} />
              <th className="px-4 py-2 font-medium">Seat</th>
              <SortHeader label="Predicted footfall" k="predicted" sort={sort} onSort={onSort} align="right" />
              <th className="px-4 py-2 text-right font-medium">Actual footfall</th>
              <th className="px-4 py-2 text-right font-medium">Paid</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sorted.map((w) => (
              <tr key={w.auction_id}>
                <td className="px-4 py-2 font-medium">{w.pole_code}</td>
                <td className="whitespace-nowrap px-4 py-2">
                  {shortDate(w.date)} <span className="text-slate-500">· {w.shift_label}</span>
                </td>
                <td className="px-4 py-2">{w.seat}</td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                  {w.predicted_low !== null && w.predicted_high !== null ? `${formatNumber(w.predicted_low)}–${formatNumber(w.predicted_high)}` : '—'}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {w.slot_status === 'done' && w.actual_footfall !== null ? (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="font-medium">{formatNumber(w.actual_footfall)}</span>
                      <Versus actual={w.actual_footfall} predicted={w.predicted_footfall} low={w.predicted_low} high={w.predicted_high} />
                    </span>
                  ) : w.slot_status === 'live' && w.live_footfall !== null ? (
                    <span className="inline-flex items-center gap-1.5" title="Counted so far; updates while the slot runs">
                      <span className="relative flex size-2">
                        <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75" />
                        <span className="relative inline-flex size-2 rounded-full bg-red-500" />
                      </span>
                      <span className="text-[11px] font-semibold uppercase tracking-wide text-red-600">Live</span>
                      <span className="font-medium">{formatNumber(w.live_footfall)}</span>
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">upcoming</span>
                  )}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">{formatINR(w.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
