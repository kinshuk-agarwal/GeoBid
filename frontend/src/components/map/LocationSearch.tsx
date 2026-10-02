import { MapPin, Route, Search, X } from 'lucide-react'
import { useId, useMemo, useRef, useState } from 'react'

import type { Pole, Road } from '@/types'
import { CATEGORY } from '@/utils/category'
import { footfallRange } from '@/utils/format'
import { LOCALITIES, type Locality } from '@/utils/localities'

export type SearchResult =
  | { kind: 'locality'; locality: Locality }
  | { kind: 'pole'; pole: Pole }
  | { kind: 'road'; road: Road }

interface Props {
  poles: Pole[]
  roads: Road[]
  onPick: (r: SearchResult) => void
}

const MAX_PER_GROUP = 5

function matches(q: string, ...fields: (string | null | undefined)[]) {
  return fields.some((f) => f?.toLowerCase().includes(q))
}

export function LocationSearch({ poles, roads, onPick }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listId = useId()

  const results = useMemo<SearchResult[]>(() => {
    const q = query.trim().toLowerCase()
    if (!q) return LOCALITIES.slice(0, 6).map((locality) => ({ kind: 'locality', locality }))
    return [
      ...LOCALITIES.filter((l) => matches(q, l.name))
        .slice(0, MAX_PER_GROUP)
        .map((locality): SearchResult => ({ kind: 'locality', locality })),
      ...poles
        .filter((p) => matches(q, p.code, p.name, p.road_name))
        .slice(0, MAX_PER_GROUP)
        .map((pole): SearchResult => ({ kind: 'pole', pole })),
      ...roads
        .filter((r) => matches(q, r.name))
        .slice(0, MAX_PER_GROUP)
        .map((road): SearchResult => ({ kind: 'road', road })),
    ]
  }, [query, poles, roads])

  const pick = (r: SearchResult) => {
    onPick(r)
    setQuery('')
    setOpen(false)
    inputRef.current?.blur()
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && results[active]) {
      e.preventDefault()
      pick(results[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
      <input
        ref={inputRef}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setActive(0)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={onKeyDown}
        placeholder="Search area, pole or road"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-8 pr-8 text-sm placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
      />
      {query && (
        <button
          aria-label="Clear search"
          onClick={() => setQuery('')}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:text-slate-700"
        >
          <X className="size-4" />
        </button>
      )}

      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-[1200] mt-1 max-h-80 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {results.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">No matches</li>}
          {results.map((r, i) => (
            <li
              key={r.kind + (r.kind === 'pole' ? r.pole.code : r.kind === 'road' ? r.road.id : r.locality.name)}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(r)}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-center gap-2.5 px-3 py-1.5 text-sm ${i === active ? 'bg-slate-100' : ''}`}
            >
              {r.kind === 'locality' && (
                <>
                  <MapPin className="size-4 text-slate-400" />
                  <span>{r.locality.name}</span>
                  <span className="ml-auto text-xs text-slate-400">Locality</span>
                </>
              )}
              {r.kind === 'pole' && (
                <>
                  <span className="size-2.5 rounded-full" style={{ background: CATEGORY[r.pole.category].color }} />
                  <span className="font-medium">{r.pole.code}</span>
                  <span className="truncate text-slate-500">{r.pole.name}</span>
                  <span className="ml-auto text-xs tabular-nums text-slate-400">{footfallRange(r.pole.footfall)}</span>
                </>
              )}
              {r.kind === 'road' && (
                <>
                  <Route className="size-4 text-slate-400" />
                  <span className="truncate">{r.road.name}</span>
                  <span className="ml-auto text-xs text-slate-400">Road</span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
