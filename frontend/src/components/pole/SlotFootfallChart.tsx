import { Footprints } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { FootfallProfile } from '@/types'
import { footfallRange } from '@/utils/format'

// Single series, one hue (palette slot 1): the selected slot is the full step,
// the rest a lighter step of the same hue. Text stays in slate.
const SERIES = '#2a78d6'
const SERIES_MUTED = '#b9d3f3'
const GRID = '#e2e8f0'
const AXIS_TEXT = '#64748b'

interface Props {
  profile: FootfallProfile
  selectedShift: string | null
  onSelectShift: (shift: string) => void
}

/** Footfall in each 2-hour slot of one day (synthetic model output). */
export function SlotFootfallChart({ profile, selectedShift, onSelectShift }: Props) {
  const data = profile.slots.map((s) => ({ ...s, hour: s.label.slice(0, 2) }))
  return (
    <section className="rounded-lg border border-slate-200 p-3">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
          <Footprints className="size-3.5 text-slate-500" /> Footfall by 2-hour slot
        </h4>
        <span className="text-[11px] text-slate-500">
          {profile.weekday} total {footfallRange(profile.daily_total)}
        </span>
      </div>
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 6, right: 0, bottom: 0, left: -18 }} barCategoryGap={2}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="hour" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS_TEXT }} interval={1} />
            <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: AXIS_TEXT }} width={44}
              tickFormatter={(n: number) => (n >= 1000 ? `${+(n / 1000).toFixed(1)}k` : String(n))} />
            <Tooltip
              cursor={{ fill: 'rgba(148,163,184,0.12)' }}
              content={({ active, payload }) => {
                const s = active && payload?.[0]?.payload
                if (!s) return null
                return (
                  <div className="rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-200">
                    <div className="mb-1 font-medium text-slate-500">
                      {profile.weekday} {s.label}
                    </div>
                    <div className="flex justify-between gap-4">
                      <span className="text-slate-500">Footfall</span>
                      <span className="font-semibold tabular-nums text-slate-900">{footfallRange(s.footfall)}</span>
                    </div>
                    <div className="flex justify-between gap-4">
                      <span className="text-slate-500">Share of day</span>
                      <span className="font-semibold tabular-nums text-slate-900">{(s.share * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                )
              }}
            />
            <Bar
              dataKey="footfall"
              radius={[3, 3, 0, 0]}
              isAnimationActive={false}
              cursor="pointer"
              onClick={(item) => {
                const code = (item as { payload?: { shift?: string } }).payload?.shift
                if (code) onSelectShift(code)
              }}
            >
              {data.map((s) => (
                <Cell key={s.shift} fill={s.shift === selectedShift ? SERIES : SERIES_MUTED} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-1 text-xs">
        <summary className="cursor-pointer text-slate-500 hover:text-slate-800">Show as table</summary>
        <table className="mt-2 w-full text-left tabular-nums">
          <tbody className="divide-y divide-slate-100">
            {profile.slots.map((s) => (
              <tr key={s.shift} className={s.shift === selectedShift ? 'font-semibold' : ''}>
                <td className="py-1">{s.label}</td>
                <td className="py-1 text-right">{footfallRange(s.footfall)}</td>
                <td className="py-1 text-right text-slate-500">{(s.share * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}
