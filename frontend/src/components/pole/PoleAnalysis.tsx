import { AlertTriangle, Maximize2, RotateCw, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { dashboardApi } from '@/api'
import { errorMessage } from '@/api/client'
import { RevenueChart } from '@/components/dashboard/RevenueChart'
import type { Pole, PoleAnalysisData } from '@/types'
import { footfallRange, formatINR, formatNumber } from '@/utils/format'

import { CategoryBadge } from '../common/CategoryBadge'
import { SyntheticNotice } from '../common/SyntheticNotice'
import { AuctionControls } from './AuctionControls'

interface Props {
  pole: Pick<Pole, 'code' | 'road_name' | 'category' | 'footfall' | 'visibility_score'> & { rank?: number | null }
  /** Shown next to the rank; omit where the rank isn't known. */
  totalPoles?: number
  onClose?: () => void
  /** Hide the "open full page" link when already on the full page. */
  standalone?: boolean
}

const pct = (x: number) => `${Math.round(x * 100)}%`

/** The admin's view of a pole: status, performance and auction controls (no bidding). */
export function PoleAnalysis({ pole, totalPoles, onClose, standalone = false }: Props) {
  const [data, setData] = useState<PoleAnalysisData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let live = true
    // Keep the current numbers on screen while refreshing the same pole (e.g. after an auction action).
    setData((d) => (d && d.code === pole.code ? d : null))
    setError(null)
    dashboardApi
      .poleAnalysis(pole.code)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(errorMessage(e, 'Could not load analysis')))
    return () => {
      live = false
    }
  }, [pole.code, reloadKey])

  const k = data?.kpis
  const peak = data ? Math.max(...data.slots.map((s) => s.avg_footfall)) : 0

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold tracking-tight">{pole.code}</h2>
            <CategoryBadge category={pole.category} />
            {data && (
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${
                  data.status === 'ACTIVE' ? 'bg-emerald-50 text-emerald-800 ring-emerald-200' : 'bg-slate-100 text-slate-500 ring-slate-200'
                }`}
              >
                {data.status === 'ACTIVE' ? 'Active' : 'Inactive'}
              </span>
            )}
          </div>
          <p className="truncate text-sm text-slate-600">{pole.road_name}</p>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-0.5">
          {!standalone && (
            <Link to={`/poles/${pole.code}`} title="Open full page" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <Maximize2 className="size-4" />
            </Link>
          )}
          {onClose && (
            <button onClick={onClose} aria-label="Close pole analysis" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <X className="size-4" />
            </button>
          )}
        </div>
      </div>

      {/* Pole facts (public) */}
      <div className="grid grid-cols-3 divide-x divide-slate-100 rounded-lg border border-slate-200 text-center">
        <Stat label="Footfall" value={footfallRange(pole.footfall)} sub="per day" />
        {pole.rank ? (
          <Stat label="Rank" value={`#${pole.rank}`} sub={totalPoles ? `of ${totalPoles}` : undefined} />
        ) : (
          <Stat label="Category" value={pole.category.charAt(0) + pole.category.slice(1).toLowerCase()} sub="footfall" />
        )}
        <Stat label="Visibility" value={`${pole.visibility_score}`} sub="/ 100" />
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800">
          <div className="flex items-center gap-1.5 font-medium">
            <AlertTriangle className="size-3.5" /> {error}
          </div>
          <button onClick={() => setReloadKey((n) => n + 1)} className="mt-2 inline-flex items-center gap-1 underline">
            <RotateCw className="size-3" /> Retry
          </button>
        </div>
      ) : !data || !k ? (
        <div className="h-96 animate-pulse rounded-lg bg-slate-50" aria-label="Loading analysis" />
      ) : (
        <>
          {/* Status */}
          <dl className="space-y-1 rounded-lg border border-slate-200 p-3 text-xs">
            <Row label="Footfall score" value={`${data.footfall_score} / 100`} />
            <Row label="On sale" value={`${data.open_slots} slots over the next 7 days`} />
          </dl>

          {/* Performance */}
          <div className="grid grid-cols-2 gap-2">
            <Tile label="Revenue" value={formatINR(k.revenue_total)} sub={`${formatINR(k.revenue_30d)} last 30 days`} />
            <Tile label="Seats sold" value={formatNumber(k.seats_sold)} sub={k.avg_seat_price ? `avg ${formatINR(k.avg_seat_price)} / seat` : 'none yet'} />
            <Tile label="Sell-through" value={pct(k.sell_through)} sub={`slots sold, last ${data.window_days} days`} />
            <Tile label="Price vs base" value={k.price_vs_base ? `${k.price_vs_base.toFixed(2)}×` : '—'} sub="avg selling ÷ base price" />
          </div>

          <AuctionControls poleCode={pole.code} onChanged={() => setReloadKey((n) => n + 1)} />

          <section className="rounded-lg border border-slate-200 p-3">
            <h4 className="mb-1 text-xs font-semibold text-slate-700">Booked revenue · last 30 days</h4>
            <RevenueChart data={data.revenue_by_day} height={120} />
          </section>

          {/* Per-slot performance */}
          <section className="rounded-lg border border-slate-200">
            <h4 className="border-b border-slate-100 px-3 py-2 text-xs font-semibold text-slate-700">By 2-hour slot</h4>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[11px] text-slate-500">
                  <th className="px-3 py-1.5 font-medium">Slot</th>
                  <th className="px-2 py-1.5 font-medium">Footfall</th>
                  <th className="px-2 py-1.5 text-right font-medium">Base</th>
                  <th className="px-2 py-1.5 text-right font-medium">Avg sold</th>
                  <th className="px-3 py-1.5 text-right font-medium">Sold</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.slots.map((s) => (
                  <tr key={s.shift}>
                    <td className="whitespace-nowrap px-3 py-1.5 tabular-nums text-slate-700">{s.label.slice(0, 5)}</td>
                    <td className="px-2 py-1.5">
                      <div className="flex items-center gap-1.5">
                        <div className="h-1.5 w-10 rounded-full bg-slate-100">
                          <div className="h-1.5 rounded-full bg-[#2a78d6]" style={{ width: `${peak ? (s.avg_footfall / peak) * 100 : 0}%` }} />
                        </div>
                        <span className="tabular-nums text-slate-600">{footfallRange(s.avg_footfall)}</span>
                      </div>
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{formatINR(s.base_price)}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{s.avg_price ? formatINR(s.avg_price) : '—'}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{pct(s.sell_through)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="border-t border-slate-100 px-3 py-1.5 text-[11px] text-slate-500">
              Footfall is the weekday average; base price is tomorrow’s; avg sold and sold % cover the last {data.window_days} days.
            </p>
          </section>
        </>
      )}

      <SyntheticNotice compact />
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="px-2 py-2">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="text-sm font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-[10px] text-slate-400">{sub}</div>}
    </div>
  )
}

function Tile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border border-slate-200 px-3 py-2">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="text-base font-semibold tabular-nums">{value}</div>
      <div className="truncate text-[10px] text-slate-400">{sub}</div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  )
}
