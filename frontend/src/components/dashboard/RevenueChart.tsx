import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { RevenuePoint } from '@/types'
import { formatINR } from '@/utils/format'

// Single series: one hue (palette slot 1); text and axes stay slate.
const SERIES = '#2a78d6'
const GRID = '#e2e8f0'
const AXIS = '#64748b'

const kINR = (n: number) => (n >= 1000 ? `₹${+(n / 1000).toFixed(1)}k` : `₹${n}`)
const dayLabel = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

/** Booked revenue per advertising day. */
export function RevenueChart({ data, height = 180 }: { data: RevenuePoint[]; height?: number }) {
  const rows = data.map((p) => ({ ...p, label: dayLabel(p.date) }))
  return (
    <div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 6, right: 0, bottom: 0, left: -6 }} barCategoryGap={3}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS }} interval="preserveStartEnd" minTickGap={16} />
            <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS }} tickFormatter={kINR} width={52} />
            <Tooltip
              cursor={{ fill: 'rgba(148,163,184,0.12)' }}
              content={({ active, payload }) => {
                const p = active && payload?.[0]?.payload
                if (!p) return null
                return (
                  <div className="rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-200">
                    <div className="mb-1 font-medium text-slate-500">{p.label}</div>
                    <div className="font-semibold tabular-nums">{formatINR(p.revenue)}</div>
                    <div className="text-slate-500">{p.seats} seats booked</div>
                  </div>
                )
              }}
            />
            <Bar dataKey="revenue" fill={SERIES} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-1 text-xs">
        <summary className="cursor-pointer text-slate-500 hover:text-slate-800">Show as table</summary>
        <table className="mt-2 w-full tabular-nums">
          <tbody className="divide-y divide-slate-100">
            {rows.map((p) => (
              <tr key={p.date}>
                <td className="py-1">{p.label}</td>
                <td className="py-1 text-right">{formatINR(p.revenue)}</td>
                <td className="py-1 text-right text-slate-500">{p.seats} seats</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
