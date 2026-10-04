import { useEffect, useState } from 'react'

/** Milliseconds until `target`, ticking every `tickMs` (default 1 s), corrected by `clockOffset`. */
export function useCountdown(target: string | null | undefined, clockOffset = 0, tickMs = 1000): number {
  const compute = () => (target ? Math.max(0, new Date(target).getTime() - (Date.now() + clockOffset)) : 0)
  const [remaining, setRemaining] = useState(compute)

  useEffect(() => {
    setRemaining(compute())
    if (!target) return
    const t = setInterval(() => setRemaining(compute()), tickMs)
    return () => clearInterval(t)
    // `compute` only reads target and clockOffset
  }, [target, clockOffset, tickMs])

  return remaining
}

export function formatDuration(ms: number): string {
  const total = Math.ceil(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
}

/** A rough duration for tables: "2 days+", "10 hrs+", "45 min", "<1 min". */
export function formatCoarse(ms: number): string {
  const min = Math.floor(ms / 60_000)
  if (min < 1) return ms > 0 ? '<1 min' : 'now'
  if (min < 60) return `${min} min`
  const hrs = Math.floor(min / 60)
  if (hrs < 48) return `${hrs} ${hrs === 1 ? 'hr' : 'hrs'}+`
  return `${Math.floor(hrs / 24)} days+`
}
