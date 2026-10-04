import { FastForward, Play, Plus, Square } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { adminApi, polesApi } from '@/api'
import { errorMessage } from '@/api/client'
import { EndsIn } from '@/components/dashboard/AuctionTable'
import { useToast } from '@/hooks/useToast'
import type { AuctionBrief, PoleInventory, Slot } from '@/types'
import { ROUND } from '@/utils/inventory'

import { ConfirmButton } from '../common/ConfirmButton'

const DAYS_AHEAD = 7

function isoDay(offset: number): string {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toLocaleDateString('en-CA')
}

function dayChip(iso: string, i: number) {
  const [y, m, d] = iso.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  return {
    top: i === 0 ? 'Tmrw' : date.toLocaleDateString('en-IN', { weekday: 'short' }),
    bottom: date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
  }
}

const NEXT_ROUND: Record<string, string> = {
  QUALIFYING: 'Close qualifying',
  BREAK: 'Open premium',
  PREMIUM: 'Close auction',
}

/** The auctioneer's controls for one pole: open, advance and close each slot's auction. */
export function AuctionControls({ poleCode, onChanged }: { poleCode: string; onChanged?: () => void }) {
  const { notify } = useToast()
  const days = useMemo(() => Array.from({ length: DAYS_AHEAD }, (_, i) => isoDay(i + 1)), [])
  const [day, setDay] = useState(days[0])
  const [inventory, setInventory] = useState<PoleInventory | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const ctrl = new AbortController()
    setError(null)
    polesApi
      .inventory(poleCode, day, ctrl.signal)
      .then(setInventory)
      .catch((e) => !ctrl.signal.aborted && setError(errorMessage(e, 'Could not load auctions')))
    return () => ctrl.abort()
  }, [poleCode, day, reloadKey])

  const act = async (fn: () => Promise<unknown>, title: string) => {
    try {
      await fn()
      notify({ tone: 'success', title })
      setReloadKey((k) => k + 1)
      onChanged?.()
    } catch (e) {
      notify({ tone: 'warning', title: 'Action failed', body: errorMessage(e) })
    }
  }

  const actions = (s: Slot, a: AuctionBrief | null) => {
    const what = `${poleCode} ${s.shift_label}`
    if (!a) {
      return s.status === 'AVAILABLE' ? (
        <ConfirmButton label="Create" icon={<Plus className="size-3" />}
          onConfirm={() => act(() => adminApi.createAuction({ inventory_slot_id: s.id }), `Auction created for ${what}`)} />
      ) : null
    }
    if (a.status === 'SCHEDULED') {
      return (
        <ConfirmButton label="Open" icon={<Play className="size-3" />} primary
          onConfirm={() => act(() => adminApi.start(a.id), `${what}: qualifying round opened`)} />
      )
    }
    if (a.status !== 'LIVE' || !a.round) return null
    return (
      <span className="inline-flex gap-1">
        <ConfirmButton label={NEXT_ROUND[a.round] ?? 'Next round'} icon={<FastForward className="size-3" />} primary
          onConfirm={() => act(() => adminApi.advance(a.id), `${what}: ${NEXT_ROUND[a.round!]?.toLowerCase() ?? 'advanced'}`)} />
        {a.round !== 'PREMIUM' && (
          <ConfirmButton label="End now" confirmLabel="End auction?" icon={<Square className="size-3" />}
            onConfirm={() => act(() => adminApi.complete(a.id), `${what}: auction closed`)} />
        )}
      </span>
    )
  }

  return (
    <section className="rounded-lg border border-slate-200">
      <h4 className="border-b border-slate-100 px-3 py-2 text-xs font-semibold text-slate-700">Auction control</h4>
      <div className="space-y-2 p-3">
        <div role="tablist" aria-label="Auction date" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
          {days.map((d, i) => {
            const c = dayChip(d, i)
            const active = d === day
            return (
              <button key={d} role="tab" aria-selected={active} onClick={() => setDay(d)}
                className={`flex min-w-[3rem] flex-col items-center rounded-lg px-2 py-1 text-[11px] ${
                  active ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                <span className="font-semibold">{c.top}</span>
                <span className={active ? 'text-slate-300' : 'text-slate-500'}>{c.bottom}</span>
              </button>
            )
          })}
        </div>

        {error ? (
          <p className="text-xs text-red-700">{error}</p>
        ) : !inventory ? (
          <div className="h-64 animate-pulse rounded-lg bg-slate-50" aria-label="Loading auctions" />
        ) : (
          <ul className="divide-y divide-slate-100 text-xs">
            {inventory.slots.map((s) => {
              const a = s.auction
              const filled = a ? a.seats.filter((x) => x.advertiser_id !== null).length : 0
              const action = actions(s, a)
              return (
                <li key={s.id} className="py-2">
                  <div className="flex items-center gap-2">
                    <span className="w-10 shrink-0 tabular-nums font-medium text-slate-700">{s.shift_label.slice(0, 5)}</span>
                    <Status a={a} />
                    {a?.status === 'LIVE' && (
                      <span className="ml-auto whitespace-nowrap text-[11px] text-slate-500" title="Seats filled · time until the round moves on by itself">
                        {filled}/4 seats · <EndsIn iso={a.round_ends_at} />
                      </span>
                    )}
                  </div>
                  {action && <div className="mt-1.5 pl-12">{action}</div>}
                </li>
              )
            })}
          </ul>
        )}
        <p className="text-[10px] text-slate-500">
          The timer shows when the round moves on by itself (12:00 and 16:00 the day before). Buttons need a second click to confirm.
        </p>
      </div>
    </section>
  )
}

function Status({ a }: { a: AuctionBrief | null }) {
  if (!a) return <span className="text-slate-400">No auction</span>
  if (a.status === 'SCHEDULED') return <span className="text-slate-600">Scheduled</span>
  if (a.status === 'COMPLETED') return <span className="text-slate-500">Closed</span>
  if (a.status === 'CANCELLED') return <span className="text-slate-500">Cancelled</span>
  if (!a.round || a.round === 'CLOSED') return <span className="text-slate-500">Closed</span>
  const r = ROUND[a.round]
  return <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${r.className}`}>{r.label}</span>
}
