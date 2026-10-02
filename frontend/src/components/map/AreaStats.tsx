import type { MapResponse } from '@/types'
import { CATEGORY, CATEGORY_ORDER } from '@/utils/category'
import { footfallRange, formatNumber } from '@/utils/format'

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="px-3 py-2.5">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="truncate text-base font-semibold tabular-nums tracking-tight">{value}</div>
      {sub && <div className="truncate text-[11px] text-slate-400">{sub}</div>}
    </div>
  )
}

/** Summary of the poles inside the current radius. */
export function AreaStats({ data }: { data: MapResponse }) {
  const poles = data.poles
  const total = data.counts.total
  const avg = Math.round(poles.reduce((s, p) => s + p.footfall, 0) / Math.max(total, 1))
  const top = poles.reduce((best, p) => (p.footfall > best.footfall ? p : best), poles[0])

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 divide-x divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200 [&>*:nth-child(3)]:border-l-0">
        <Stat label="Poles in radius" value={formatNumber(total)} sub={`${data.roads.length} major roads`} />
        <Stat label="Avg daily footfall" value={footfallRange(avg)} />
        <Stat label="Top footfall" value={footfallRange(top.footfall)} sub={`${top.code} · ${top.name.replace(/^Near /, '')}`} />
        <Stat
          label="High-footfall poles"
          value={formatNumber(data.counts.HIGH)}
          sub={`${Math.round((100 * data.counts.HIGH) / Math.max(total, 1))}% of area`}
        />
      </div>

      <div>
        <div className="flex h-2 overflow-hidden rounded-full bg-slate-100">
          {CATEGORY_ORDER.map((c) => (
            <div
              key={c}
              style={{ width: `${(100 * data.counts[c]) / Math.max(total, 1)}%`, background: CATEGORY[c].color }}
              title={`${CATEGORY[c].label}: ${data.counts[c]}`}
            />
          ))}
        </div>
        <div className="mt-1.5 flex justify-between text-[11px] text-slate-500">
          {CATEGORY_ORDER.map((c) => (
            <span key={c} className="inline-flex items-center gap-1">
              <span className="size-2 rounded-full" style={{ background: CATEGORY[c].color }} />
              {c.charAt(0) + c.slice(1).toLowerCase()} {data.counts[c]}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
