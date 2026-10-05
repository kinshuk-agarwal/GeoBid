import { AlertTriangle, Film, Pause, Play, RotateCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'

import { videosApi } from '@/api'
import { API_BASE_URL, errorMessage } from '@/api/client'
import { PageSpinner } from '@/components/common/Spinner'
import type { Video } from '@/types'

const duration = (s: number | null) => {
  if (s === null) return null
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.round(s % 60)).padStart(2, '0')}`
}
const megabytes = (b: number) => `${(b / 1_048_576).toFixed(1)} MB`

/** Footfall camera footage: the raw input and the annotated detection output. */
export function VideosPage() {
  const [videos, setVideos] = useState<Video[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [params, setParams] = useSearchParams()
  const player = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    setError(null)
    videosApi
      .list()
      .then(setVideos)
      .catch((e) => setError(errorMessage(e, 'Could not load videos')))
  }, [reloadKey])

  if (error && !videos) {
    return (
      <div className="mx-auto max-w-md p-8 text-sm text-red-800">
        <p className="flex items-center gap-1.5 font-medium">
          <AlertTriangle className="size-4" /> {error}
        </p>
        <button onClick={() => setReloadKey((k) => k + 1)} className="mt-2 inline-flex items-center gap-1 underline">
          <RotateCw className="size-3.5" /> Retry
        </button>
      </div>
    )
  }
  if (!videos) return <PageSpinner />

  // ?video=N (1-based, matching the "Video N" titles); defaults to the first.
  const index = Math.min(Math.max(Number(params.get('video')) || 1, 1), Math.max(videos.length, 1)) - 1
  const current = videos[index] ?? null
  const choose = (i: number) => setParams({ video: String(i + 1) }, { replace: true })
  const toggle = () => {
    const v = player.current
    if (!v) return
    if (v.paused) void v.play()
    else v.pause()
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-5 px-4 py-6">
        <header>
          <h1 className="text-xl font-semibold tracking-tight">Footfall videos</h1>
          <p className="text-sm text-slate-500">Camera footage behind the footfall counts.</p>
        </header>

        {videos.length === 0 || !current ? (
          <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">No videos yet.</p>
        ) : (
          <div className="grid gap-5 lg:grid-cols-[1fr_18rem]">
            <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
              <div className="relative flex justify-center bg-slate-950">
                {/* Doesn't autoplay: the viewer starts it with the play button or the controls. */}
                <video
                  key={current.name}
                  ref={player}
                  src={`${API_BASE_URL}${current.url}`}
                  controls
                  playsInline
                  preload="metadata"
                  onPlay={() => setPlaying(true)}
                  onPause={() => setPlaying(false)}
                  onEnded={() => setPlaying(false)}
                  onLoadStart={() => setPlaying(false)}
                  className="max-h-[70vh] w-full object-contain"
                  aria-label={current.title}
                />
                {!playing && (
                  <button
                    onClick={toggle}
                    aria-label={`Play ${current.title}`}
                    className="absolute inset-0 m-auto flex size-16 items-center justify-center rounded-full bg-white/90 text-slate-900 shadow-lg transition hover:scale-105 hover:bg-white"
                  >
                    <Play className="ml-1 size-7 fill-current" />
                  </button>
                )}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                <div className="flex items-center gap-3">
                  <button
                    onClick={toggle}
                    className="inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
                  >
                    {playing ? <Pause className="size-4 fill-current" /> : <Play className="size-4 fill-current" />}
                    {playing ? 'Pause' : 'Play'}
                  </button>
                  <h2 className="text-sm font-semibold">{current.title}</h2>
                </div>
                <span className="text-xs text-slate-500">
                  {[duration(current.duration_s), current.width && `${current.width}×${current.height}`, megabytes(current.size_bytes)]
                    .filter(Boolean)
                    .join(' · ')}
                </span>
              </div>
            </section>

            <nav aria-label="Videos" className="space-y-1.5">
              {videos.map((v, i) => {
                const active = v.name === current.name
                return (
                  <button
                    key={v.name}
                    onClick={() => choose(i)}
                    aria-current={active}
                    className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors ${
                      active ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <Film className={`size-4 shrink-0 ${active ? 'text-slate-300' : 'text-slate-400'}`} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{v.title}</span>
                      <span className={`block text-xs ${active ? 'text-slate-300' : 'text-slate-500'}`}>
                        {[duration(v.duration_s), v.width && (v.height! > v.width ? 'Portrait' : 'Landscape')].filter(Boolean).join(' · ')}
                      </span>
                    </span>
                  </button>
                )
              })}
            </nav>
          </div>
        )}
      </div>
    </div>
  )
}
