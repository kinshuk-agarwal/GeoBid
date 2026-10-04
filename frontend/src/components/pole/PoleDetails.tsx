import { AlertTriangle, BookOpen, Maximize2, RotateCw, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { polesApi } from '@/api'
import { errorMessage } from '@/api/client'
import type { FootfallProfile, Pole, PoleInventory, Slot } from '@/types'
import { footfallRange, formatINR } from '@/utils/format'
import { DEMAND } from '@/utils/inventory'

import { BidModal } from '../auction/BidModal'
import { CategoryBadge } from '../common/CategoryBadge'
import { BiddingGuideModal } from './BiddingGuide'
import { PriceTrendPanel } from './PriceTrendPanel'
import { SlotFootfallChart } from './SlotFootfallChart'
import { SlotList } from './SlotList'

const DAYS_AHEAD = 7

function TariffBreakdown({ slot, pole }: { slot: Slot; pole: Pole }) {
  const t = slot.tariff
  const rows: [string, string][] = [
    ['Standard rate', formatINR(t.base_rate)],
    [`× Pole value (${pole.footfall_score} footfall, ${pole.visibility_score} visibility scores)`, t.pole_multiplier.toFixed(2)],
    t.basis === 'slot_footfall' && t.slot_footfall !== null && t.avg_slot_footfall
      ? [`× Slot footfall (${(t.slot_footfall / t.avg_slot_footfall).toFixed(2)}× this pole's average slot)`, t.shift_multiplier.toFixed(2)]
      : [`× ${DEMAND[t.demand].label} demand`, t.shift_multiplier.toFixed(2)],
  ]
  return (
    <dl className="space-y-1 rounded-lg bg-white p-3 text-xs ring-1 ring-slate-200">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-3">
          <dt className="text-slate-600">{label}</dt>
          <dd className="font-medium tabular-nums">{value}</dd>
        </div>
      ))}
      <div className="flex justify-between border-t border-slate-100 pt-1">
        <dt className="font-medium">= Base price</dt>
        <dd className="font-semibold tabular-nums">{formatINR(slot.reserve_price)}</dd>
      </div>
    </dl>
  )
}

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

interface Props {
  pole: Pole
  totalPoles: number
  onClose?: () => void
  /** Hide the "open full page" link when already on the full page. */
  standalone?: boolean
}

export function PoleDetails({ pole, totalPoles, onClose, standalone = false }: Props) {
  const days = useMemo(() => Array.from({ length: DAYS_AHEAD }, (_, i) => isoDay(i + 1)), [])
  const [day, setDay] = useState(days[0])
  const [inventory, setInventory] = useState<PoleInventory | null>(null)
  const [profile, setProfile] = useState<FootfallProfile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [selectedSlotId, setSelectedSlotId] = useState<number | null>(null)
  const [bidAuctionId, setBidAuctionId] = useState<number | null>(null)
  const [guideOpen, setGuideOpen] = useState(false)

  useEffect(() => {
    const ctrl = new AbortController()
    setProfile(null)
    polesApi
      .footfallProfile(pole.code, day, ctrl.signal)
      .then(setProfile)
      .catch(() => undefined) // optional; the panel works without it
    return () => ctrl.abort()
  }, [pole.code, day])

  useEffect(() => {
    const ctrl = new AbortController()
    setError(null)
    polesApi
      .inventory(pole.code, day, ctrl.signal)
      .then((inv) => {
        setInventory(inv)
        // Keep the open slot across refreshes; otherwise open the busiest biddable one.
        setSelectedSlotId((current) => {
          if (current && inv.slots.some((s) => s.id === current)) return current
          const biddable = inv.slots.filter((s) => s.auction?.round === 'QUALIFYING' || s.auction?.round === 'PREMIUM')
          const pool = biddable.length ? biddable : inv.slots
          return [...pool].sort((a, b) => b.reserve_price - a.reserve_price)[0]?.id ?? null
        })
      })
      .catch((e) => !ctrl.signal.aborted && setError(errorMessage(e, 'Could not load slots')))
    return () => ctrl.abort()
  }, [pole.code, day, reloadKey])

  const selectedSlot = inventory?.slots.find((s) => s.id === selectedSlotId) ?? null
  const peak = profile?.slots.find((s) => s.shift === profile.peak_shift) ?? null
  const closeBid = useCallback(() => {
    setBidAuctionId(null)
    setReloadKey((k) => k + 1) // pick up any bids placed in the popup
  }, [])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold tracking-tight">{pole.code}</h2>
            <CategoryBadge category={pole.category} />
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
            <button onClick={onClose} aria-label="Close pole details" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <X className="size-4" />
            </button>
          )}
        </div>
      </div>

      {/* Key stats */}
      <div className="grid grid-cols-3 divide-x divide-slate-100 rounded-lg border border-slate-200 text-center">
        <Stat label="Peak slot" value={peak ? footfallRange(peak.footfall) : footfallRange(pole.footfall)} sub={peak?.label ?? 'per day'} />
        <Stat label="Rank" value={pole.rank ? `#${pole.rank}` : '—'} sub={`of ${totalPoles}`} />
        <Stat label="Visibility" value={`${pole.visibility_score}`} sub="/ 100" />
      </div>

      {/* 7-day strip */}
      <div role="tablist" aria-label="Advertising date" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
        {days.map((d, i) => {
          const c = dayChip(d, i)
          const active = d === day
          return (
            <button
              key={d}
              role="tab"
              aria-selected={active}
              onClick={() => {
                setDay(d)
                setSelectedSlotId(null)
              }}
              className={`flex min-w-[3.25rem] flex-col items-center rounded-lg px-2 py-1 text-xs ${
                active ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              <span className="font-semibold">{c.top}</span>
              <span className={active ? 'text-slate-300' : 'text-slate-500'}>{c.bottom}</span>
            </button>
          )
        })}
      </div>

      {profile && (
        <SlotFootfallChart
          profile={profile}
          selectedShift={selectedSlot?.shift ?? null}
          onSelectShift={(code) => {
            const slot = inventory?.slots.find((s) => s.shift === code)
            if (slot) setSelectedSlotId(slot.id)
          }}
        />
      )}

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800">
          <div className="flex items-center gap-1.5 font-medium">
            <AlertTriangle className="size-3.5" /> {error}
          </div>
          <button onClick={() => setReloadKey((k) => k + 1)} className="mt-2 inline-flex items-center gap-1 underline">
            <RotateCw className="size-3" /> Retry
          </button>
        </div>
      ) : !inventory ? (
        <div className="h-96 animate-pulse rounded-lg bg-slate-50" aria-label="Loading slots" />
      ) : inventory.slots.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">No slots on this date.</p>
      ) : (
        <SlotList
          slots={inventory.slots}
          selectedId={selectedSlotId}
          onSelect={(s) => setSelectedSlotId(s?.id ?? null)}
          onBid={setBidAuctionId}
          renderDetails={(slot) => (
            <div className="space-y-3">
              <TariffBreakdown slot={slot} pole={pole} />
              <PriceTrendPanel poleCode={pole.code} shift={slot.shift} date={slot.date} />
            </div>
          )}
        />
      )}

      <button
        onClick={() => setGuideOpen(true)}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-sky-700 underline-offset-2 hover:underline"
      >
        <BookOpen className="size-4" /> How bidding works: price formulas and rounds
      </button>


      {bidAuctionId !== null && <BidModal auctionId={bidAuctionId} onClose={closeBid} />}
      {guideOpen && <BiddingGuideModal onClose={() => setGuideOpen(false)} />}
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
