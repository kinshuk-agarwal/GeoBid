import {
  AlertTriangle,
  Crosshair,
  Gavel,
  LocateFixed,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  RotateCw,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'

import { polesApi } from '@/api'
import { Spinner } from '@/components/common/Spinner'
import { SyntheticNotice } from '@/components/common/SyntheticNotice'
import { AreaStats } from '@/components/map/AreaStats'
import { LocationSearch, type SearchResult } from '@/components/map/LocationSearch'
import { MapLegend } from '@/components/map/MapLegend'
import { PoleMap, radiusBounds, type FocusRequest, type FocusTarget } from '@/components/map/PoleMap'
import { RadiusSelector } from '@/components/map/RadiusSelector'
import { TopPoles } from '@/components/map/TopPoles'
import { BiddingGuide } from '@/components/pole/BiddingGuide'
import { PoleAnalysis } from '@/components/pole/PoleAnalysis'
import { PoleDetails } from '@/components/pole/PoleDetails'
import { useAuth } from '@/hooks/useAuth'
import { useMapData } from '@/hooks/useMapData'
import type { FootfallCategory, LatLng, Pole } from '@/types'
import { haversineKm } from '@/utils/geo'
import { DEFAULT_LOCATION, DEFAULT_RADIUS_KM, RADIUS_OPTIONS } from '@/utils/mapDefaults'

function readCenter(params: URLSearchParams): LatLng & { name: string } {
  const lat = Number(params.get('lat'))
  const lng = Number(params.get('lng'))
  if (params.has('lat') && params.has('lng') && Number.isFinite(lat) && Number.isFinite(lng)) {
    return { latitude: lat, longitude: lng, name: params.get('loc') || 'Custom area' }
  }
  return DEFAULT_LOCATION
}

export function MapPage() {
  const [params, setParams] = useSearchParams()
  const center = readCenter(params)
  const radiusParam = Number(params.get('radius'))
  const radius = RADIUS_OPTIONS.includes(radiusParam) ? radiusParam : DEFAULT_RADIUS_KM
  const selectedCode = params.get('pole')
  const { user } = useAuth()
  // Admins don't bid: a pole opens its analysis and auction controls instead.
  const analyst = user?.role === 'ADMIN'

  const { data, loading, error, reload } = useMapData(center.latitude, center.longitude, radius)
  const [allPoles, setAllPoles] = useState<Pole[]>([])
  const [hidden, setHidden] = useState<Set<FootfallCategory>>(new Set())
  const [focus, setFocus] = useState<FocusTarget | null>(null)
  const [viewCenter, setViewCenter] = useState<LatLng | null>(null)
  // Below the xl breakpoint the right panel is an overlay; the guide opens on demand.
  const [guideOpen, setGuideOpen] = useState(false)

  useEffect(() => {
    polesApi.list().then(setAllPoles).catch(() => setAllPoles([]))
  }, [])

  const updateParams = useCallback(
    (changes: Record<string, string | null>) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [k, v] of Object.entries(changes)) {
            if (v === null) next.delete(k)
            else next.set(k, v)
          }
          return next
        },
        { replace: true },
      ),
    [setParams],
  )

  const focusOn = useCallback((t: FocusRequest) => setFocus({ ...t, nonce: Date.now() }), [])

  const setCenter = (lat: number, lng: number, name: string) => {
    updateParams({ lat: lat.toFixed(5), lng: lng.toFixed(5), loc: name })
    focusOn({ kind: 'bounds', bounds: radiusBounds(lat, lng, radius) })
  }

  const selectPole = (pole: Pole) => {
    // Recentre on the pole if it lies outside the current radius.
    const outside = haversineKm(center, pole) > radius
    updateParams({
      pole: pole.code,
      ...(outside && { lat: pole.latitude.toFixed(5), lng: pole.longitude.toFixed(5), loc: pole.code }),
    })
    focusOn({ kind: 'point', latitude: pole.latitude, longitude: pole.longitude, zoom: 16 })
  }

  const changeRadius = (km: number) => {
    updateParams({ radius: String(km) })
    focusOn({ kind: 'bounds', bounds: radiusBounds(center.latitude, center.longitude, km) })
  }

  const onSearchPick = (r: SearchResult) => {
    if (r.kind === 'locality') setCenter(r.locality.latitude, r.locality.longitude, r.locality.name)
    else if (r.kind === 'pole') selectPole(r.pole)
    else focusOn({ kind: 'bounds', bounds: r.road.path })
  }

  // Focus a pole passed in the URL (e.g. /map?pole=P014) once data arrives.
  const initialFocusDone = useRef(false)
  useEffect(() => {
    if (initialFocusDone.current || !data || !selectedCode) return
    const p = data.poles.find((x) => x.code === selectedCode)
    if (p) focusOn({ kind: 'point', latitude: p.latitude, longitude: p.longitude, zoom: 16 })
    initialFocusDone.current = true
  }, [data, selectedCode, focusOn])

  const selectedPole = useMemo(
    () => data?.poles.find((p) => p.code === selectedCode) ?? allPoles.find((p) => p.code === selectedCode) ?? null,
    [data, allPoles, selectedCode],
  )

  const toggleCategory = (c: FootfallCategory) =>
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(c)) next.delete(c)
      else next.add(c)
      return next
    })

  const movedAway = viewCenter !== null && haversineKm(viewCenter, center) > Math.max(0.75, radius * 0.15)
  const isDefaultCenter =
    center.latitude === DEFAULT_LOCATION.latitude && center.longitude === DEFAULT_LOCATION.longitude
  const counts = data?.counts ?? {}
  const totalPoles = allPoles.length || data?.counts.total || 0
  const panelOpen = selectedPole !== null || guideOpen
  // Both side panels can be collapsed to a slim rail (desktop widths).
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)

  const closePanel = () => {
    setGuideOpen(false)
    updateParams({ pole: null })
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto lg:flex-row lg:overflow-hidden">
      {/* Left: area stats + top poles */}
      {!leftOpen && (
        <Rail side="left" label="Show top poles" onClick={() => setLeftOpen(true)} />
      )}
      <aside
        className={`order-2 w-full shrink-0 flex-col border-slate-200 bg-white lg:order-1 lg:h-full lg:w-[320px] lg:border-r ${
          leftOpen ? 'flex' : 'flex lg:hidden'
        }`}
      >
        <div className="border-b border-slate-100 px-4 py-3">
          <div className="flex items-center justify-between">
            <h1 className="text-base font-semibold tracking-tight">Top poles</h1>
            <button
              onClick={() => setLeftOpen(false)}
              aria-label="Collapse top poles"
              title="Collapse"
              className="hidden rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 lg:inline-flex"
            >
              <PanelLeftClose className="size-4" />
            </button>
          </div>
          <p className="flex items-center gap-1 text-sm text-slate-500">
            <LocateFixed className="size-3.5 shrink-0" />
            <span className="truncate">
              {center.name} · {radius} km
            </span>
            {!isDefaultCenter && (
              <button
                onClick={() => setCenter(DEFAULT_LOCATION.latitude, DEFAULT_LOCATION.longitude, DEFAULT_LOCATION.name)}
                className="ml-auto shrink-0 text-xs font-medium text-slate-600 underline-offset-2 hover:underline"
              >
                Reset
              </button>
            )}
          </p>
        </div>

        <div className="flex-1 space-y-5 p-4 lg:overflow-y-auto">
          {error && !data ? (
            <ErrorState message={error} onRetry={reload} />
          ) : !data ? (
            <SidebarSkeleton />
          ) : data.poles.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center">
              <p className="text-sm font-medium">No poles within {radius} km</p>
              <p className="mt-1 text-xs text-slate-500">Try a larger radius or search another locality.</p>
            </div>
          ) : (
            <>
              <AreaStats data={data} />
              <TopPoles
                top={data.top}
                counts={counts}
                hidden={hidden}
                selectedCode={selectedCode}
                onSelect={selectPole}
              />
            </>
          )}
        </div>

        <div className="border-t border-slate-100 px-4 py-2.5">
          <SyntheticNotice compact />
        </div>
      </aside>

      {/* Centre map + right panel */}
      <div className="relative order-1 flex h-[70vh] shrink-0 lg:order-2 lg:h-full lg:min-w-0 lg:flex-1">
        <section className="relative min-w-0 flex-1">
          <PoleMap
            center={center}
            radiusKm={radius}
            roads={data?.roads ?? []}
            poles={data?.poles ?? []}
            hiddenCategories={hidden}
            selectedCode={selectedCode}
            focus={focus}
            onSelect={selectPole}
            onViewChange={setViewCenter}
            layoutKey={`${leftOpen}-${rightOpen}-${panelOpen}`}
          />

          {/* Toolbar: search + radius */}
          <div className="absolute inset-x-3 top-3 z-[1000] flex flex-wrap items-start gap-2 sm:right-auto">
            <div className="flex w-full flex-col gap-2 rounded-xl bg-white/95 p-2 shadow-md ring-1 ring-slate-200 backdrop-blur sm:w-auto sm:flex-row sm:items-center">
              <div className="sm:w-72">
                <LocationSearch poles={allPoles} roads={data?.roads ?? []} onPick={onSearchPick} />
              </div>
              <RadiusSelector value={radius} options={RADIUS_OPTIONS} onChange={changeRadius} />
            </div>
          </div>

          {!analyst && (
          <button
            onClick={() => setGuideOpen(true)}
            className="absolute right-3 top-3 z-[1000] hidden items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-sm font-medium shadow-md ring-1 ring-slate-200 hover:bg-slate-50 sm:inline-flex xl:hidden"
          >
            <Gavel className="size-4" /> How to bid
          </button>
          )}

          <div className="absolute bottom-6 left-3 z-[1000]">
            <MapLegend counts={counts} hidden={hidden} onToggle={toggleCategory} />
          </div>

          <div className="pointer-events-none absolute inset-x-0 bottom-6 z-[1000] flex justify-center gap-2 px-36">
            {loading && data && (
              <span className="pointer-events-auto inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-medium shadow-md ring-1 ring-slate-200">
                <Spinner className="size-3" /> Updating…
              </span>
            )}
            {!loading && movedAway && viewCenter && (
              <button
                onClick={() => setCenter(viewCenter.latitude, viewCenter.longitude, 'Custom area')}
                className="pointer-events-auto inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-slate-900 px-3.5 py-1.5 text-xs font-medium text-white shadow-md hover:bg-slate-800"
              >
                <Crosshair className="size-3.5" /> Search this area
              </button>
            )}
            {error && data && (
              <span className="pointer-events-auto inline-flex items-center gap-2 rounded-full bg-red-50 px-3 py-1.5 text-xs font-medium text-red-800 shadow-md ring-1 ring-red-200">
                <AlertTriangle className="size-3.5" /> {error}
                <button onClick={reload} className="underline">
                  Retry
                </button>
              </span>
            )}
          </div>
        </section>

        {/* Right: pole details or bidding guide. Docked at xl (collapsible), overlay below. */}
        {!rightOpen && (
          <div className="hidden xl:flex">
            <Rail side="right" label="Show details" onClick={() => setRightOpen(true)} />
          </div>
        )}
        <aside
          className={`${panelOpen ? 'flex' : 'hidden'} absolute inset-y-0 right-0 z-[1050] w-full flex-col border-l border-slate-200 bg-white shadow-xl sm:w-[400px] xl:relative xl:z-auto xl:shadow-none ${
            rightOpen ? 'xl:flex' : 'xl:hidden'
          }`}
          aria-label={selectedPole ? `Pole ${selectedPole.code} details` : analyst ? 'Pole analysis' : 'How bidding works'}
        >
          <button
            onClick={() => setRightOpen(false)}
            aria-label="Collapse details"
            title="Collapse"
            className="absolute left-2 top-2 z-10 hidden rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 xl:inline-flex"
          >
            <PanelRightClose className="size-4" />
          </button>
          <div className="flex-1 overflow-y-auto p-5 xl:pt-9">
            {selectedPole ? (
              analyst ? (
                <PoleAnalysis key={selectedPole.code} pole={selectedPole} totalPoles={totalPoles} onClose={closePanel} />
              ) : (
                <PoleDetails key={selectedPole.code} pole={selectedPole} totalPoles={totalPoles} onClose={closePanel} />
              )
            ) : analyst ? (
              <div className="py-10 text-center text-sm text-slate-500">
                <p className="font-medium text-slate-700">Pole analysis</p>
                <p className="mt-1">Select a pole on the map to see its status and performance and to run its auctions.</p>
              </div>
            ) : (
              <div className="relative">
                <button
                  onClick={closePanel}
                  aria-label="Close guide"
                  className="absolute right-0 top-0 rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 xl:hidden"
                >
                  <X className="size-4" />
                </button>
                <BiddingGuide />
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}

function Rail({ side, label, onClick }: { side: 'left' | 'right'; label: string; onClick: () => void }) {
  const Icon = side === 'left' ? PanelLeftOpen : PanelRightOpen
  return (
    <div
      className={`hidden h-full w-10 shrink-0 flex-col items-center border-slate-200 bg-white py-3 lg:flex ${
        side === 'left' ? 'order-1 border-r' : 'border-l'
      }`}
    >
      <button onClick={onClick} aria-label={label} title={label} className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900">
        <Icon className="size-4" />
      </button>
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <div className="flex items-center gap-2 font-medium">
        <AlertTriangle className="size-4" /> Couldn't load poles
      </div>
      <p className="mt-1 text-xs">{message}</p>
      <button
        onClick={onRetry}
        className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-white px-2.5 py-1 text-xs font-medium ring-1 ring-red-200 hover:bg-red-100"
      >
        <RotateCw className="size-3.5" /> Retry
      </button>
    </div>
  )
}

function SidebarSkeleton() {
  return (
    <div className="animate-pulse space-y-5" aria-label="Loading">
      <div className="h-32 rounded-lg bg-slate-100" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="space-y-2">
          <div className="h-3 w-32 rounded bg-slate-100" />
          {[0, 1, 2].map((j) => (
            <div key={j} className="h-8 rounded-md bg-slate-100" />
          ))}
        </div>
      ))}
    </div>
  )
}
