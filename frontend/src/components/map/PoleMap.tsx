import L, { type LatLngBoundsExpression } from 'leaflet'
import { useEffect, useMemo } from 'react'
import {
  Circle,
  CircleMarker,
  MapContainer,
  Polyline,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
  useMapEvents,
} from 'react-leaflet'

import { API_BASE_URL } from '@/api/client'
import type { FootfallCategory, Pole, Road } from '@/types'
import { CATEGORY } from '@/utils/category'
import { footfallRange } from '@/utils/format'

// OpenStreetMap tiles, served through the backend's caching proxy (/tiles) so
// every tile is fetched from OSM once, with a proper User-Agent, per OSM's tile
// usage policy. Desaturated in CSS (.gb-basemap) so the pole markers stand out.
// Override with VITE_MAP_TILE_URL / VITE_MAP_TILE_ATTRIBUTION.
const TILE_URL = import.meta.env.VITE_MAP_TILE_URL ?? `${API_BASE_URL}/tiles/{z}/{x}/{y}.png`
const TILE_ATTRIBUTION =
  import.meta.env.VITE_MAP_TILE_ATTRIBUTION ??
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

export type FocusRequest =
  | { kind: 'point'; latitude: number; longitude: number; zoom?: number }
  | { kind: 'bounds'; bounds: LatLngBoundsExpression }

/** A focus request plus a nonce so repeating the same request still fires. */
export type FocusTarget = FocusRequest & { nonce: number }

export function radiusBounds(lat: number, lng: number, radiusKm: number): L.LatLngBounds {
  return L.latLng(lat, lng).toBounds(radiusKm * 2000)
}

interface Props {
  center: { latitude: number; longitude: number }
  radiusKm: number
  roads: Road[]
  poles: Pole[]
  hiddenCategories: Set<FootfallCategory>
  selectedCode: string | null
  focus: FocusTarget | null
  onSelect: (pole: Pole) => void
  onViewChange: (center: { latitude: number; longitude: number }) => void
  /** changes whenever surrounding panels resize, so Leaflet re-measures */
  layoutKey?: string
}

/** Moves the map in response to focus requests from outside the map. */
function MapController({ focus }: { focus: FocusTarget | null }) {
  const map = useMap()
  useEffect(() => {
    if (!focus) return
    if (focus.kind === 'point') {
      map.flyTo([focus.latitude, focus.longitude], focus.zoom ?? Math.max(map.getZoom(), 15), { duration: 0.8 })
    } else {
      map.flyToBounds(focus.bounds, { padding: [24, 24], duration: 0.8 })
    }
  }, [focus?.nonce]) // only react to new focus requests
  return null
}

/** Leaflet caches its container size; re-measure after side panels open or close. */
function ResizeWatcher({ layoutKey }: { layoutKey?: string }) {
  const map = useMap()
  useEffect(() => {
    const t = setTimeout(() => map.invalidateSize({ pan: false }), 220)
    return () => clearTimeout(t)
  }, [layoutKey, map])
  return null
}

/** Reports the map centre after the user drags (not after programmatic flights). */
function ViewWatcher({ onViewChange }: { onViewChange: Props['onViewChange'] }) {
  useMapEvents({
    dragend: (e) => {
      const c = e.target.getCenter()
      onViewChange({ latitude: c.lat, longitude: c.lng })
    },
  })
  return null
}

function RoadLayer({ roads, highlightId }: { roads: Road[]; highlightId: number | null }) {
  return (
    <>
      {/* White casing underneath gives roads a map-like outline. */}
      {roads.map((road) => (
        <Polyline
          key={`casing-${road.id}`}
          positions={road.path}
          pathOptions={{ color: '#ffffff', weight: 5 + road.importance_score / 30, opacity: 0.9, lineCap: 'round' }}
          interactive={false}
        />
      ))}
      {roads.map((road) => {
        const highlighted = road.id === highlightId
        return (
          <Polyline
            key={road.id}
            positions={road.path}
            pathOptions={{
              color: highlighted ? '#1e293b' : '#64748b',
              weight: 2 + road.importance_score / 30,
              opacity: highlighted ? 0.95 : 0.6,
              lineCap: 'round',
            }}
          >
            <Tooltip sticky className="gb-tooltip">
              {road.name}
            </Tooltip>
          </Polyline>
        )
      })}
    </>
  )
}

function PoleMarker({ pole, selected, onSelect }: { pole: Pole; selected: boolean; onSelect: (p: Pole) => void }) {
  const c = CATEGORY[pole.category]
  return (
    <CircleMarker
      center={[pole.latitude, pole.longitude]}
      radius={selected ? 11 : pole.category === 'HIGH' ? 8 : 7}
      pathOptions={{
        color: selected ? '#0f172a' : c.stroke,
        weight: selected ? 3 : 1.5,
        fillColor: c.color,
        fillOpacity: 0.95,
      }}
      eventHandlers={{ click: () => onSelect(pole) }}
    >
      <Tooltip direction="top" offset={[0, -8]} className="gb-tooltip">
        {pole.code} · {footfallRange(pole.footfall)} / day
      </Tooltip>
    </CircleMarker>
  )
}

export function PoleMap({
  center,
  radiusKm,
  roads,
  poles,
  hiddenCategories,
  selectedCode,
  focus,
  onSelect,
  onViewChange,
  layoutKey,
}: Props) {
  // Initial view only; later moves go through `focus`.
  const initialBounds = useMemo(() => radiusBounds(center.latitude, center.longitude, radiusKm), [])

  // Draw lower categories first and the selected pole last so the most
  // valuable poles sit on top where markers overlap.
  const visible = useMemo(() => {
    const order: Record<FootfallCategory, number> = { LOW: 0, MEDIUM: 1, HIGH: 2 }
    return poles
      .filter((p) => !hiddenCategories.has(p.category))
      .sort((a, b) => order[a.category] - order[b.category] || a.footfall - b.footfall)
      .sort((a, b) => Number(a.code === selectedCode) - Number(b.code === selectedCode))
  }, [poles, hiddenCategories, selectedCode])

  const selectedRoadId = poles.find((p) => p.code === selectedCode)?.road_id ?? null

  return (
    <MapContainer bounds={initialBounds} className="size-full" zoomControl={false} minZoom={11}>
      <ZoomControl position="bottomright" />
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} maxZoom={19} className="gb-basemap" />
      <Circle
        center={[center.latitude, center.longitude]}
        radius={radiusKm * 1000}
        pathOptions={{ color: '#334155', weight: 1.5, dashArray: '6 6', fillColor: '#334155', fillOpacity: 0.035 }}
        interactive={false}
      />
      <CircleMarker
        center={[center.latitude, center.longitude]}
        radius={4}
        pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#0f172a', fillOpacity: 1 }}
        interactive={false}
      />
      <RoadLayer roads={roads} highlightId={selectedRoadId} />
      {visible.map((p) => (
        <PoleMarker key={p.id} pole={p} selected={p.code === selectedCode} onSelect={onSelect} />
      ))}
      <MapController focus={focus} />
      <ViewWatcher onViewChange={onViewChange} />
      <ResizeWatcher layoutKey={layoutKey} />
    </MapContainer>
  )
}
