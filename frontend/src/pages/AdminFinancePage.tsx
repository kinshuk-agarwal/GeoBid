import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { useCallback } from 'react'
import { useSearchParams } from 'react-router'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { dashboardApi } from '@/api'
import { CategoryDot } from '@/components/common/CategoryBadge'
import { PageSpinner } from '@/components/common/Spinner'
import { Section } from '@/components/dashboard/Kpi'
import { usePolling } from '@/hooks/usePolling'
import type { FinanceDashboardData, FinanceGranularity, PeriodTotal } from '@/types'
import { CATEGORY } from '@/utils/category'
import { formatINR, formatINRCompact, formatNumber } from '@/utils/format'

// Chart roles (validated palette, light surface): qualifying = series 1 (blue),
// premium = series 2 (orange); single-series charts use series 1. Text stays slate.
const QUALIFYING = '#2a78d6'
const PREMIUM = '#eb6834'
const SURFACE = '#ffffff'
const GRID = '#e2e8f0'
const AXIS = '#64748b'

const PERIODS = [
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 180, label: '6 months' },
  { days: 0, label: 'All time' },
]
const VIEWS: { key: FinanceGranularity; label: string }[] = [
  { key: 'day', label: 'Daily' },
  { key: 'week', label: 'Weekly' },
  { key: 'month', label: 'Monthly' },
]

const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`

function parseDay(iso: string) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}
function bucketLabel(iso: string, g: FinanceGranularity) {
  const d = parseDay(iso)
  if (g === 'month') return d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
function bucketTitle(iso: string, g: FinanceGranularity) {
  const d = parseDay(iso)
  if (g === 'month') return d.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
  if (g === 'week') return `Week of ${d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}`
  return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
}
const shortDay = (iso: string) => parseDay(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

/** Last day of the bucket starting at ``iso``. */
function bucketEnd(iso: string, g: FinanceGranularity) {
  const d = parseDay(iso)
  if (g === 'week') d.setDate(d.getDate() + 6)
  if (g === 'month') d.setMonth(d.getMonth() + 1, 0)
  return d
}

/** The admin's finance view: revenue over time, who and what earns the most. */
export function AdminFinancePage() {
  const [params, setParams] = useSearchParams()
  const days = PERIODS.some((p) => String(p.days) === params.get('days')) ? Number(params.get('days')) : 90
  const view: FinanceGranularity = VIEWS.some((v) => v.key === params.get('view')) ? (params.get('view') as FinanceGranularity) : 'week'
  const set = (key: string, value: string) =>
    setParams(
      (p) => {
        p.set(key, value)
        return p
      },
      { replace: true },
    )

  const load = useCallback(() => dashboardApi.finance(days, view), [days, view])
  const { data, error } = usePolling(load, [days, view], 60_000)

  if (error && !data) return <p className="p-8 text-sm text-red-700">{error}</p>
  if (!data) return <PageSpinner />
  const k = data.kpis
  const windowLabel = PERIODS.find((p) => p.days === days)?.label.toLowerCase() ?? ''

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-5 px-4 py-6">
        <header className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Finance</h1>
            <p className="text-sm text-slate-500">
              Booked revenue by advertising date. Each seat pays its own winning bid; there are no costs in this model, so revenue is profit.
            </p>
          </div>
          <span className="text-xs text-slate-400">As of {shortDay(data.as_of)} · refreshes every minute</span>
        </header>

        {/* Headline revenue: fixed periods, independent of the filters below */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <PeriodTile label="Today so far" period={k.today} compare="all of yesterday" />
          <PeriodTile label="Last 7 days" period={k.last_7_days} compare="previous 7 days" />
          <PeriodTile label="Last 30 days" period={k.last_30_days} compare="previous 30 days" />
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
            <div className="text-xs text-slate-500">All time</div>
            <div className="mt-0.5 text-2xl font-semibold tracking-tight">{formatINRCompact(k.all_time_revenue)}</div>
            <div className="text-xs text-slate-500">{formatNumber(k.all_time_seats)} seats sold</div>
          </div>
        </div>

        {/* One filter row for everything below */}
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-2.5">
          <Segmented label="Period" options={PERIODS.map((p) => ({ key: String(p.days), label: p.label }))} value={String(days)} onChange={(v) => set('days', v)} />
          <Segmented label="View" options={VIEWS} value={view} onChange={(v) => set('view', v)} />
          <span className="ml-auto text-xs text-slate-400">
            {shortDay(data.window_start)} – {shortDay(data.window_end)}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Average seat price" value={k.avg_seat_price ? formatINR(k.avg_seat_price) : '—'} />
          <Stat label="Seats filled" value={pct(k.seat_fill_rate)} sub="of seats offered in closed auctions" />
          <Stat label="Premium round share" value={pct(k.premium_share)} sub="of revenue" />
          <Stat label="Active buyers" value={formatNumber(k.active_buyers)} sub={`${pct(k.repeat_buyer_rate)} bought on 2+ days`} />
        </div>

        <Section title={`${VIEWS.find((v) => v.key === view)?.label} revenue · ${windowLabel}`}>
          <RevenueTrend data={data} />
        </Section>

        <div className="grid gap-5 lg:grid-cols-2">
          <Section title={`Top advertisers by revenue · ${windowLabel}`}>
            <RankTable
              rows={data.top_advertisers.map((a) => ({
                key: String(a.advertiser_id),
                name: a.name,
                value: a.revenue,
                share: a.share,
                detail: `${formatNumber(a.seats)} seats · avg ${formatINR(a.avg_price)}`,
              }))}
            />
          </Section>
          <Section title={`Top poles by revenue · ${windowLabel}`}>
            <RankTable
              rows={data.top_poles.map((p) => ({
                key: p.code,
                name: (
                  <span className="inline-flex min-w-0 items-center gap-1.5">
                    <CategoryDot category={p.category} />
                    <span className="font-semibold">{p.code}</span>
                    <span className="truncate text-xs font-normal text-slate-500">{p.road_name}</span>
                  </span>
                ),
                value: p.revenue,
                share: p.share,
                detail: `${formatNumber(p.seats)} seats · ${pct(p.fill_rate)} filled`,
              }))}
            />
          </Section>
        </div>

        <Section title={`Frequent buyers · ${windowLabel}`}>
          <FrequentBuyers data={data} />
        </Section>

        <div className="grid gap-5 lg:grid-cols-[3fr_2fr]">
          <Section title="Revenue by time of day">
            <SlotChart data={data} />
          </Section>
          <Section title="Revenue by pole footfall">
            <div className="space-y-3">
              {data.by_category.map((c) => (
                <div key={c.category}>
                  <div className="mb-1 flex items-baseline justify-between text-sm">
                    <span className="inline-flex items-center gap-1.5 font-medium">
                      <CategoryDot category={c.category} /> {CATEGORY[c.category].label}
                    </span>
                    <span className="tabular-nums">
                      {formatINRCompact(c.revenue)} <span className="text-xs text-slate-500">· {pct(c.share)}</span>
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100">
                    <div className="h-2 rounded-full" style={{ width: `${c.share * 100}%`, background: QUALIFYING }} />
                  </div>
                  <div className="mt-0.5 text-[11px] text-slate-500">{formatNumber(c.seats)} seats</div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      </div>
    </div>
  )
}

// --- pieces ----------------------------------------------------------------------

function PeriodTile({ label, period, compare }: { label: string; period: PeriodTotal; compare: string }) {
  const { revenue, previous_revenue: prev } = period
  const change = prev > 0 ? (revenue - prev) / prev : null
  const Icon = change === null || Math.abs(change) < 0.005 ? Minus : change > 0 ? ArrowUpRight : ArrowDownRight
  const tone = change === null || Math.abs(change) < 0.005 ? 'text-slate-500' : change > 0 ? 'text-emerald-700' : 'text-red-700'
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-0.5 text-2xl font-semibold tracking-tight">{formatINRCompact(revenue)}</div>
      <div className={`flex items-center gap-0.5 text-xs ${tone}`}>
        <Icon className="size-3.5" aria-hidden />
        {change === null ? `no sales ${compare}` : `${change > 0 ? '+' : ''}${pct(change)} vs ${compare}`}
      </div>
      <div className="text-[11px] text-slate-400">{formatNumber(period.seats)} {period.seats === 1 ? 'seat' : 'seats'}</div>
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-0.5 text-lg font-semibold">{value}</div>
      {sub && <div className="text-[11px] text-slate-400">{sub}</div>}
    </div>
  )
}

function Segmented<K extends string>({ label, options, value, onChange }: { label: string; options: { key: K; label: string }[]; value: K; onChange: (v: K) => void }) {
  return (
    <div className="flex items-center gap-2" role="group" aria-label={label}>
      <span className="text-xs text-slate-500">{label}</span>
      <div className="flex rounded-lg bg-slate-100 p-0.5">
        {options.map((o) => (
          <button
            key={o.key}
            onClick={() => onChange(o.key)}
            aria-pressed={o.key === value}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              o.key === value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function Legend() {
  return (
    <div className="flex gap-4 text-xs text-slate-600">
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm" style={{ background: QUALIFYING }} /> Qualifying round
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm" style={{ background: PREMIUM }} /> Premium round
      </span>
    </div>
  )
}

function RevenueTrend({ data }: { data: FinanceDashboardData }) {
  const g = data.granularity
  // A bucket is partial when the window cuts it or it hasn't finished yet (today is in progress).
  const from = parseDay(data.window_start)
  const to = parseDay(data.window_end)
  const rows = data.revenue.map((b) => ({
    ...b,
    total: b.qualifying + b.premium,
    label: bucketLabel(b.start, g),
    partial: parseDay(b.start) < from || bucketEnd(b.start, g) >= to,
  }))
  const anyPartial = rows.some((r) => r.partial)
  const total = rows.reduce((s, r) => s + r.total, 0)
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Legend />
        <span className="text-xs text-slate-500">
          Total <span className="font-semibold text-slate-800">{formatINR(total)}</span>
        </span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 6, right: 0, bottom: 0, left: 0 }} barCategoryGap={rows.length > 40 ? 1 : 4}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS }} interval="preserveStartEnd" minTickGap={18} />
            <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS }} tickFormatter={formatINRCompact} width={64} />
            <Tooltip
              cursor={{ fill: 'rgba(148,163,184,0.14)' }}
              content={({ active, payload }) => {
                const p = active && (payload?.[0]?.payload as (typeof rows)[number] | undefined)
                if (!p) return null
                return (
                  <div className="min-w-44 rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-200">
                    <div className="mb-1 font-medium text-slate-500">
                      {bucketTitle(p.start, g)}
                      {p.partial && <span className="ml-1 text-slate-400">(partial)</span>}
                    </div>
                    <div className="flex justify-between gap-4 font-semibold tabular-nums">
                      <span>Total</span> {formatINR(p.total)}
                    </div>
                    <TipRow color={QUALIFYING} label="Qualifying" value={p.qualifying} />
                    <TipRow color={PREMIUM} label="Premium" value={p.premium} />
                    <div className="mt-1 text-slate-500">{formatNumber(p.seats)} seats sold</div>
                  </div>
                )
              }}
            />
            <Bar dataKey="qualifying" stackId="r" fill={QUALIFYING} stroke={SURFACE} strokeWidth={1} isAnimationActive={false}>
              {rows.map((r) => (
                <Cell key={r.start} fillOpacity={r.partial ? 0.4 : 1} />
              ))}
            </Bar>
            <Bar dataKey="premium" stackId="r" fill={PREMIUM} stroke={SURFACE} strokeWidth={1} radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {rows.map((r) => (
                <Cell key={r.start} fillOpacity={r.partial ? 0.4 : 1} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {anyPartial && (
        <p className="text-[11px] text-slate-500">Faded bars are partial periods: cut off by the date range, or still in progress.</p>
      )}
      <details className="text-xs">
        <summary className="cursor-pointer text-slate-500 hover:text-slate-800">Show as table</summary>
        <div className="mt-2 max-h-72 overflow-y-auto">
          <table className="w-full tabular-nums">
            <thead className="sticky top-0 bg-white text-left text-slate-500">
              <tr>
                <th className="py-1 font-medium">Period</th>
                <th className="py-1 text-right font-medium">Qualifying</th>
                <th className="py-1 text-right font-medium">Premium</th>
                <th className="py-1 text-right font-medium">Total</th>
                <th className="py-1 text-right font-medium">Seats</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r) => (
                <tr key={r.start}>
                  <td className="py-1">
                    {bucketTitle(r.start, g)}
                    {r.partial && <span className="text-slate-400"> (partial)</span>}
                  </td>
                  <td className="py-1 text-right">{formatINR(r.qualifying)}</td>
                  <td className="py-1 text-right">{formatINR(r.premium)}</td>
                  <td className="py-1 text-right font-medium">{formatINR(r.total)}</td>
                  <td className="py-1 text-right text-slate-500">{formatNumber(r.seats)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}

function TipRow({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-4 tabular-nums text-slate-700">
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2 rounded-sm" style={{ background: color }} /> {label}
      </span>
      {formatINR(value)}
    </div>
  )
}

/** Ranked list with an inline share bar (one hue: magnitude, not identity). */
function RankTable({ rows }: { rows: { key: string; name: React.ReactNode; value: number; share: number; detail: string }[] }) {
  if (rows.length === 0) return <p className="py-6 text-center text-sm text-slate-500">No sales in this period.</p>
  const max = Math.max(...rows.map((r) => r.value), 1)
  return (
    <ol className="space-y-2.5">
      {rows.map((r, i) => (
        <li key={r.key} className="grid grid-cols-[1.25rem_1fr_auto] items-center gap-x-2">
          <span className="text-xs tabular-nums text-slate-400">{i + 1}</span>
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{r.name}</div>
            <div className="mt-1 h-1.5 rounded-full bg-slate-100">
              <div className="h-1.5 rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: QUALIFYING }} />
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm font-semibold tabular-nums">{formatINRCompact(r.value)}</div>
            <div className="text-[11px] text-slate-500">{pct(r.share, 1)} share</div>
          </div>
          <div className="col-start-2 col-end-4 text-[11px] text-slate-500">{r.detail}</div>
        </li>
      ))}
    </ol>
  )
}

function FrequentBuyers({ data }: { data: FinanceDashboardData }) {
  const rows = data.frequent_buyers
  if (rows.length === 0) return <p className="py-6 text-center text-sm text-slate-500">No buyers in this period.</p>
  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
            <th className="px-4 py-2 font-medium">Advertiser</th>
            <th className="px-4 py-2 text-right font-medium">Buying days</th>
            <th className="px-4 py-2 text-right font-medium">Seats bought</th>
            <th className="px-4 py-2 text-right font-medium">Win rate</th>
            <th className="px-4 py-2 text-right font-medium">Spend</th>
            <th className="px-4 py-2 text-right font-medium">Avg seat</th>
            <th className="px-4 py-2 font-medium">Last purchase</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 tabular-nums">
          {rows.map((a) => (
            <tr key={a.advertiser_id}>
              <td className="px-4 py-2 font-medium">{a.name}</td>
              <td className="px-4 py-2 text-right">{formatNumber(a.purchase_days)}</td>
              <td className="px-4 py-2 text-right">{formatNumber(a.seats)}</td>
              <td className="px-4 py-2 text-right" title={`Won ${Math.round(a.win_rate * a.auctions_bid)} of ${a.auctions_bid} auctions bid on`}>
                {pct(a.win_rate)}
              </td>
              <td className="px-4 py-2 text-right">{formatINRCompact(a.revenue)}</td>
              <td className="px-4 py-2 text-right">{formatINR(a.avg_price)}</td>
              <td className="px-4 py-2 text-slate-600">{shortDay(a.last_purchase)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SlotChart({ data }: { data: FinanceDashboardData }) {
  const rows = data.by_slot.map((s) => ({ ...s, hour: s.label.slice(0, 2) }))
  return (
    <div>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 6, right: 0, bottom: 0, left: 0 }} barCategoryGap={3}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="hour" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS }} />
            <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS }} tickFormatter={formatINRCompact} width={64} />
            <Tooltip
              cursor={{ fill: 'rgba(148,163,184,0.14)' }}
              content={({ active, payload }) => {
                const p = active && (payload?.[0]?.payload as (typeof rows)[number] | undefined)
                if (!p) return null
                return (
                  <div className="rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-200">
                    <div className="mb-1 font-medium text-slate-500">{p.label}</div>
                    <div className="font-semibold tabular-nums">{formatINR(p.revenue)}</div>
                    <div className="text-slate-500">
                      {formatNumber(p.seats)} seats{p.avg_price ? ` · avg ${formatINR(p.avg_price)}` : ''}
                    </div>
                  </div>
                )
              }}
            />
            <Bar dataKey="revenue" fill={QUALIFYING} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[11px] text-slate-500">Hour the 2-hour slot starts (00 = 00:00–02:00).</p>
    </div>
  )
}
