import { TrendingUp } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { polesApi } from '@/api'
import type { PriceTrend } from '@/types'
import { formatINR, formatINRRange } from '@/utils/format'

// Single-series charts: one hue (palette slot 1). The target weekday is the
// full step; other weekdays a lighter step of the same hue. Text stays slate.
const SERIES = '#2a78d6'
const SERIES_MUTED = '#b9d3f3'
const GRID = '#e2e8f0'
const AXIS_TEXT = '#64748b'
const REF = '#64748b'

const DAY_NAME: Record<string, string> = {
  Mon: 'Mondays', Tue: 'Tuesdays', Wed: 'Wednesdays', Thu: 'Thursdays', Fri: 'Fridays', Sat: 'Saturdays', Sun: 'Sundays',
}

const kINR = (n: number) => `₹${n >= 1000 ? `${+(n / 1000).toFixed(1)}k` : n}`

function TipBox({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className="rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-200">
      <div className="mb-1 font-medium text-slate-500">{title}</div>
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-4">
          <span className="text-slate-500">{k}</span>
          <span className="font-semibold tabular-nums text-slate-900">{v}</span>
        </div>
      ))}
    </div>
  )
}

interface Props {
  poleCode: string
  shift: string
  /** advertising date (YYYY-MM-DD) whose weekday sets the expectation */
  date: string
}

export function PriceTrendPanel({ poleCode, shift, date }: Props) {
  const [trend, setTrend] = useState<PriceTrend | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const ctrl = new AbortController()
    setTrend(null)
    setError(false)
    polesApi
      .priceTrend(poleCode, shift, date, ctrl.signal)
      .then(setTrend)
      .catch(() => !ctrl.signal.aborted && setError(true))
    return () => ctrl.abort()
  }, [poleCode, shift, date])

  if (error) return <p className="text-xs text-slate-500">Price history is unavailable right now.</p>
  if (!trend) return <div className="h-64 animate-pulse rounded-lg bg-slate-50" aria-label="Loading price history" />

  const e = trend.expected
  const base = trend.points.at(-1)?.base_price ?? 0
  const targetDay = e?.weekday ?? ''
  const weekdayData = trend.by_weekday.map((w) => ({ ...w, value: w.average ?? 0 }))
  const lineData = trend.points.map((p) => ({ ...p, label: p.date.slice(5) }))
  const sold = trend.points.filter((p) => p.clearing_price !== null).length

  return (
    <section className="space-y-3 rounded-lg border border-slate-200 p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h4 className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <TrendingUp className="size-3.5 text-slate-500" /> Price history · {trend.shift_label}
          </h4>
          <p className="text-[11px] text-slate-500">
            Winning prices, last {trend.window_days} days
          </p>
        </div>
      </div>

      {/* Headline: the expected range for this weekday */}
      <div className="rounded-lg bg-slate-50 px-3 py-2.5">
        <div className="text-[11px] text-slate-500">Expected on a {targetDay || 'this day'}</div>
        {e ? (
          <>
            <div className="text-xl font-semibold tabular-nums tracking-tight">{formatINRRange(e.low, e.high)}</div>
            <div className="text-[11px] text-slate-500">
              Average {formatINR(e.average)} over the last {e.days} {DAY_NAME[e.weekday] ?? e.weekday} · sold {e.samples} of {e.days} · seen{' '}
              {formatINR(e.min_price)}–{formatINR(e.max_price)}
            </div>
          </>
        ) : (
          <div className="text-sm text-slate-500">Not enough past sales on this weekday.</div>
        )}
      </div>

      {/* Average winning price by weekday */}
      <figure>
        <figcaption className="mb-1 flex justify-between text-[11px] text-slate-600">
          <span className="font-medium">Average winning price by weekday</span>
          <span className="text-slate-500">- - - base price {formatINR(base)}</span>
        </figcaption>
        <div className="h-36">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={weekdayData} margin={{ top: 8, right: 4, bottom: 0, left: -12 }} barCategoryGap={6}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="weekday" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: AXIS_TEXT }} />
              <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS_TEXT }} tickFormatter={kINR} width={48} />
              <ReferenceLine y={base} stroke={REF} strokeDasharray="4 3" />
              <Tooltip
                cursor={{ fill: 'rgba(148,163,184,0.12)' }}
                content={({ active, payload }) => {
                  const w = active && payload?.[0]?.payload
                  if (!w) return null
                  return (
                    <TipBox
                      title={DAY_NAME[w.weekday] ?? w.weekday}
                      rows={
                        w.average === null
                          ? [['Sold', '0 days']]
                          : [
                              ['Average', formatINR(w.average)],
                              ['Range', formatINRRange(w.low, w.high)],
                              ['Sold', `${w.samples} of ${w.days} days`],
                            ]
                      }
                    />
                  )
                }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {weekdayData.map((w) => (
                  <Cell key={w.weekday} fill={w.weekday === targetDay ? SERIES : SERIES_MUTED} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </figure>

      {/* 60-day trend */}
      <figure>
        <figcaption className="mb-1 text-[11px] font-medium text-slate-600">
          Daily winning price · sold {sold} of {trend.points.length} days (gaps = unsold)
        </figcaption>
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={lineData} margin={{ top: 8, right: 4, bottom: 0, left: -12 }}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} interval={13} tick={{ fontSize: 10, fill: AXIS_TEXT }} />
              <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS_TEXT }} tickFormatter={kINR} width={48} domain={['dataMin - 500', 'dataMax + 500']} />
              <ReferenceLine y={base} stroke={REF} strokeDasharray="4 3" />
              <Tooltip
                cursor={{ stroke: '#94a3b8', strokeWidth: 1 }}
                content={({ active, payload }) => {
                  const p = active && payload?.[0]?.payload
                  if (!p) return null
                  return (
                    <TipBox
                      title={`${p.weekday} ${new Date(p.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}`}
                      rows={[
                        ['Winning price', p.clearing_price === null ? 'Unsold' : formatINR(p.clearing_price)],
                        ['Base price', formatINR(p.base_price)],
                      ]}
                    />
                  )
                }}
              />
              <Line
                type="monotone"
                dataKey="clearing_price"
                stroke={SERIES}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </figure>

      <details className="text-xs">
        <summary className="cursor-pointer text-slate-500 hover:text-slate-800">Show as table</summary>
        <table className="mt-2 w-full text-left tabular-nums">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1 font-medium">Day</th>
              <th className="py-1 font-medium">Average</th>
              <th className="py-1 font-medium">Expected range</th>
              <th className="py-1 text-right font-medium">Sold</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {trend.by_weekday.map((w) => (
              <tr key={w.weekday} className={w.weekday === targetDay ? 'font-semibold' : ''}>
                <td className="py-1">{w.weekday}</td>
                <td className="py-1">{w.average === null ? '—' : formatINR(w.average)}</td>
                <td className="py-1">{w.low === null || w.high === null ? '—' : formatINRRange(w.low, w.high)}</td>
                <td className="py-1 text-right">
                  {w.samples}/{w.days}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}
