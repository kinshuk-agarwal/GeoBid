import type { FootfallCategory } from '@/types'
import { CATEGORY, CATEGORY_ORDER } from '@/utils/category'

interface Props {
  counts: Partial<Record<FootfallCategory, number>>
  hidden: Set<FootfallCategory>
  onToggle: (c: FootfallCategory) => void
}

/** Category legend that doubles as a show/hide filter. */
export function MapLegend({ counts, hidden, onToggle }: Props) {
  return (
    <div className="rounded-lg bg-white/95 p-1.5 shadow-md ring-1 ring-slate-200 backdrop-blur">
      <div className="px-1.5 pb-1 pt-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        Footfall
      </div>
      {CATEGORY_ORDER.map((cat) => {
        const off = hidden.has(cat)
        return (
          <button
            key={cat}
            onClick={() => onToggle(cat)}
            aria-pressed={!off}
            title={off ? `Show ${CATEGORY[cat].label.toLowerCase()} poles` : `Hide ${CATEGORY[cat].label.toLowerCase()} poles`}
            className={`flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-xs hover:bg-slate-100 ${
              off ? 'text-slate-400' : 'text-slate-700'
            }`}
          >
            <span
              className="size-3 rounded-full border-[1.5px]"
              style={{
                background: off ? 'transparent' : CATEGORY[cat].color,
                borderColor: CATEGORY[cat].stroke,
              }}
            />
            <span className="font-medium">{cat.charAt(0) + cat.slice(1).toLowerCase()}</span>
            <span className="ml-auto pl-3 tabular-nums text-slate-500">{counts[cat] ?? 0}</span>
          </button>
        )
      })}
    </div>
  )
}
