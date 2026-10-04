import { useMemo } from 'react'

import type { FootfallCategory, Pole } from '@/types'
import { CATEGORY, CATEGORY_ORDER } from '@/utils/category'
import { footfallRange } from '@/utils/format'

import { CategoryDot } from '../common/CategoryBadge'

interface Props {
  /** Every pole in the radius; each category lists all of its poles, busiest first. */
  poles: Pole[]
  counts: Partial<Record<FootfallCategory, number>>
  hidden: Set<FootfallCategory>
  selectedCode: string | null
  onSelect: (pole: Pole) => void
}

const VISIBLE_ROWS = 5

export function TopPoles({ poles: all, counts, hidden, selectedCode, onSelect }: Props) {
  const byCategory = useMemo(() => {
    const out = { HIGH: [], MEDIUM: [], LOW: [] } as Record<FootfallCategory, Pole[]>
    for (const p of all) out[p.category]?.push(p)
    for (const list of Object.values(out)) list.sort((a, b) => b.footfall - a.footfall || a.code.localeCompare(b.code))
    return out
  }, [all])

  return (
    <div className="space-y-5">
      {CATEGORY_ORDER.map((cat) => {
        const poles = byCategory[cat]
        const max = Math.max(...poles.map((p) => p.footfall), 1)
        return (
          <section key={cat} className={hidden.has(cat) ? 'opacity-50' : ''}>
            <h3 className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <CategoryDot category={cat} />
              {CATEGORY[cat].label}
              <span className="ml-auto font-normal normal-case tracking-normal text-slate-400">
                {counts[cat] ?? 0} in radius
              </span>
            </h3>
            {poles.length === 0 ? (
              <p className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-500">No poles in this radius.</p>
            ) : (
              <>
              <ol
                className={`space-y-0.5 ${poles.length > VISIBLE_ROWS ? 'max-h-[16.5rem] overflow-y-auto overscroll-contain pr-1' : ''}`}
                aria-label={`${CATEGORY[cat].label} poles`}
              >
                {poles.map((p, i) => {
                  const selected = p.code === selectedCode
                  return (
                    <li key={p.id}>
                      <button
                        onClick={() => onSelect(p)}
                        className={`group grid w-full grid-cols-[1.5rem_1fr_auto] items-center gap-x-2 rounded-md px-2 py-1.5 text-left transition-colors ${
                          selected ? 'bg-slate-900 text-white' : 'hover:bg-slate-100'
                        }`}
                      >
                        <span className={`text-xs tabular-nums ${selected ? 'text-slate-300' : 'text-slate-400'}`}>
                          #{i + 1}
                        </span>
                        <span className="min-w-0 truncate">
                          <span className="text-sm font-semibold">{p.code}</span>
                          <span className={`ml-1.5 truncate text-xs ${selected ? 'text-slate-300' : 'text-slate-500'}`}>
                            {p.name.replace(/^Near /, '')}
                          </span>
                        </span>
                        <span className="text-sm font-medium tabular-nums">{footfallRange(p.footfall)}</span>
                        <span className="col-start-2 col-end-4 mt-1 h-1 overflow-hidden rounded-full bg-slate-200/70">
                          <span
                            className="block h-full rounded-full"
                            style={{ width: `${(p.footfall / max) * 100}%`, background: CATEGORY[cat].color }}
                          />
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ol>
              {poles.length > VISIBLE_ROWS && (
                <p className="mt-1 px-2 text-[11px] text-slate-400">Scroll to see all {poles.length}</p>
              )}
              </>
            )}
          </section>
        )
      })}
    </div>
  )
}
