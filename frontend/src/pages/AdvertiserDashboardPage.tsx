import { Gavel, MapPinned } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { dashboardApi, type OpportunityQuery } from '@/api'
import { BidModal } from '@/components/auction/BidModal'
import { PageSpinner } from '@/components/common/Spinner'
import { AuctionTable, COLUMNS, shortDate, type Column } from '@/components/dashboard/AuctionTable'
import { BidHistory } from '@/components/dashboard/BidHistory'
import { SeatsWon } from '@/components/dashboard/SeatsWon'
import { Empty, Kpi, KpiGrid, Section } from '@/components/dashboard/Kpi'
import { usePolling } from '@/hooks/usePolling'
import type { AdvertiserDashboardData, AuctionRow } from '@/types'
import { formatINR, formatNumber } from '@/utils/format'
import { DEFAULT_LOCATION } from '@/utils/mapDefaults'

const SEAT_LABEL: Record<string, string> = {
  CONFIRMED: 'Confirmed',
  PREMIUM: 'Premium',
}

const MY_COLUMNS: Column[] = [
  COLUMNS.pole,
  COLUMNS.slot,
  COLUMNS.round,
  {
    key: 'myseat',
    label: 'My seat',
    render: (r) =>
      r.my_seat ? (
        <span className={r.my_seat_status === 'CONFIRMED' ? 'font-medium text-emerald-700' : 'font-medium text-amber-700'}>
          Seat {r.my_seat}
          {SEAT_LABEL[r.my_seat_status ?? ''] && ` · ${SEAT_LABEL[r.my_seat_status ?? '']}`}
        </span>
      ) : (
        <span className="font-medium text-red-700">No seat</span>
      ),
  },
  { key: 'mybid', label: 'My bid', align: 'right', render: (r) => (r.my_bid ? formatINR(r.my_bid) : '—') },
  { key: 'mymin', label: 'Bid now from', align: 'right', render: (r) => (r.my_min_bid ? formatINR(r.my_min_bid) : '—') },
  COLUMNS.ends,
]

function isoDay(offset: number) {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toLocaleDateString('en-CA')
}

const SHIFT_OPTIONS = Array.from({ length: 12 }, (_, i) => {
  const h = (i * 2).toString().padStart(2, '0')
  const e = ((i * 2 + 2) % 24).toString().padStart(2, '0')
  return { value: `S${i + 1}`, label: `${h}:00–${e}:00` }
})

type TabKey = 'auctions' | 'inventory' | 'bids' | 'won'

const TABS: { key: TabKey; label: string; count: (d: AdvertiserDashboardData) => number | null }[] = [
  { key: 'auctions', label: 'My auctions', count: (d) => d.my_auctions_total },
  { key: 'inventory', label: 'Find inventory', count: () => null },
  { key: 'bids', label: 'Bid history', count: () => null },
  { key: 'won', label: 'Seats won', count: (d) => d.won.length },
]

/** Live auctions matching the filters; polls only while this tab is open. */
function Opportunities({ query, actions, refreshKey }: { query: OpportunityQuery; actions: (r: AuctionRow) => React.ReactNode; refreshKey: number }) {
  const load = useCallback(() => dashboardApi.opportunities(query), [query])
  const ops = usePolling(load, [query, refreshKey], 20_000)
  if (ops.data === null) return <PageSpinner />
  if (ops.data.length === 0) return <Empty>No live auctions match these filters.</Empty>
  return (
    <AuctionTable
      rows={ops.data}
      columns={[COLUMNS.pole, COLUMNS.slot, COLUMNS.footfall, COLUMNS.round, COLUMNS.seats, COLUMNS.min, COLUMNS.ends]}
      actions={actions}
    />
  )
}

export function AdvertiserDashboardPage() {
  const { data, error, refresh } = usePolling(dashboardApi.advertiser, [])
  const [bidOn, setBidOn] = useState<number | null>(null)
  const [bidsKey, setBidsKey] = useState(0) // reload lists after the bid popup closes
  const [params, setParams] = useSearchParams()
  const tab: TabKey = TABS.some((t) => t.key === params.get('tab')) ? (params.get('tab') as TabKey) : 'auctions'
  const setTab = (t: TabKey) => setParams((p) => { p.set('tab', t); return p }, { replace: true })
  const [filters, setFilters] = useState<OpportunityQuery>({ radius_km: 10, limit: 40 })
  const query = useMemo(
    () => ({
      ...filters,
      ...(filters.radius_km ? { latitude: DEFAULT_LOCATION.latitude, longitude: DEFAULT_LOCATION.longitude } : {}),
    }),
    [filters],
  )

  const bidButton = (r: AuctionRow) =>
    r.round === 'QUALIFYING' || r.round === 'PREMIUM' ? (
      <button
        onClick={() => setBidOn(r.id)}
        className="inline-flex items-center gap-1 rounded-md bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white hover:bg-slate-800"
      >
        <Gavel className="size-3.5" /> Bid
      </button>
    ) : (
      <button onClick={() => setBidOn(r.id)} className="rounded-md px-2.5 py-1 text-xs text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50">
        View
      </button>
    )

  if (error && !data) return <p className="p-8 text-sm text-red-700">{error}</p>
  if (!data) return <PageSpinner />
  const k = data.kpis
  const set = (patch: Partial<OpportunityQuery>) => setFilters((f) => ({ ...f, ...patch }))

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-5 px-4 py-6">
        <header className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Advertiser dashboard</h1>
            <p className="text-sm text-slate-500">Your seats, wins and what’s open to bid on.</p>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/map" className="inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800">
              <MapPinned className="size-4" /> Explore map
            </Link>
          </div>
        </header>

        <KpiGrid>
          <Kpi label="Seats held" value={formatNumber(k.seats_held)} sub={`${k.seats_at_risk} not yet confirmed`} tone={k.seats_at_risk ? 'warn' : undefined} />
          <Kpi label="Seats won" value={formatNumber(k.seats_won)} />
          <Kpi label="Total spend" value={formatINR(k.total_spend)} />
          <Kpi label="Open auctions" value={formatNumber(k.open_auctions)} sub="accepting bids now" />
        </KpiGrid>

        <nav role="tablist" aria-label="Dashboard sections" className="flex gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                tab === t.key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {t.label}
              {t.count(data) !== null && <span className="ml-1.5 text-xs text-slate-400">{formatNumber(t.count(data)!)}</span>}
            </button>
          ))}
        </nav>

        {tab === 'auctions' && (
          <Section
            title={
              data.my_auctions_total > data.my_auctions.length
                ? `My auctions · ${data.my_auctions.length} closing soonest of ${formatNumber(data.my_auctions_total)}`
                : 'My auctions'
            }
          >
            <AuctionTable rows={data.my_auctions} columns={MY_COLUMNS} actions={bidButton} empty="You haven’t bid on any live auctions." />
          </Section>
        )}

        {tab === 'inventory' && (
          <Section title="Find inventory">
            <div className="mb-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4 lg:grid-cols-8">
              <Select label="Date" value={filters.date ?? ''} onChange={(v) => set({ date: v || undefined })}
                options={[{ value: '', label: 'Any' }, ...Array.from({ length: 7 }, (_, i) => ({ value: isoDay(i + 1), label: shortDate(isoDay(i + 1)) }))]} />
              <Select label="Slot" value={filters.shift ?? ''} onChange={(v) => set({ shift: v || undefined })}
                options={[{ value: '', label: 'Any' }, ...SHIFT_OPTIONS]} />
              <Select label="Category" value={filters.category ?? ''} onChange={(v) => set({ category: v || undefined })}
                options={[{ value: '', label: 'Any' }, { value: 'HIGH', label: 'High' }, { value: 'MEDIUM', label: 'Medium' }, { value: 'LOW', label: 'Low' }]} />
              <Select label="Round" value={filters.round ?? ''} onChange={(v) => set({ round: v || undefined })}
                options={[{ value: '', label: 'Any' }, { value: 'QUALIFYING', label: 'Qualifying' }, { value: 'PREMIUM', label: 'Premium' }, { value: 'BREAK', label: 'Break' }]} />
              <Num label="Min slot footfall" value={filters.min_footfall} onChange={(v) => set({ min_footfall: v })} />
              <Num label="Min score" value={filters.min_score} onChange={(v) => set({ min_score: v })} />
              <Num label="Max price ₹" value={filters.max_price} onChange={(v) => set({ max_price: v })} />
              <Select label="Radius" value={String(filters.radius_km ?? '')} onChange={(v) => set({ radius_km: v ? Number(v) : undefined })}
                options={[{ value: '5', label: '5 km' }, { value: '10', label: '10 km' }, { value: '15', label: '15 km' }, { value: '', label: 'Any' }]} />
            </div>
            <Opportunities query={query} actions={bidButton} refreshKey={bidsKey} />
          </Section>
        )}

        {tab === 'bids' && (
          <Section title="My bid history">
            <BidHistory refreshKey={bidsKey} />
          </Section>
        )}

        {tab === 'won' && (
          <Section title="Seats won">
            {data.won.length === 0 ? (
              <Empty>No wins yet.</Empty>
            ) : (
              <SeatsWon rows={data.won} />
            )}
          </Section>
        )}
      </div>
      {bidOn !== null && (
        <BidModal
          auctionId={bidOn}
          onClose={() => {
            setBidOn(null)
            setBidsKey((k) => k + 1)
            void refresh()
          }}
        />
      )}
    </div>
  )
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-slate-500">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm">
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function Num({ label, value, onChange }: { label: string; value: number | undefined; onChange: (v: number | undefined) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-slate-500">{label}</span>
      <input
        inputMode="numeric"
        value={value ?? ''}
        onChange={(e) => {
          const n = e.target.value.replace(/[^\d]/g, '')
          onChange(n ? Number(n) : undefined)
        }}
        placeholder="Any"
        className="rounded-md border border-slate-200 px-2 py-1.5 text-sm tabular-nums"
      />
    </label>
  )
}
