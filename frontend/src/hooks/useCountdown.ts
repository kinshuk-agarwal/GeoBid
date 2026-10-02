import { useEffect, useState } from 'react'

/** Milliseconds until `target`, ticking every second, corrected by `clockOffset`. */
export function useCountdown(target: string | null | undefined, clockOffset = 0): number {
  const compute = () => (target ? Math.max(0, new Date(target).getTime() - (Date.now() + clockOffset)) : 0)
  const [remaining, setRemaining] = useState(compute)

  useEffect(() => {
    setRemaining(compute())
    if (!target) return
    const t = setInterval(() => setRemaining(compute()), 1000)
    return () => clearInterval(t)
    // `compute` only reads target and clockOffset
  }, [target, clockOffset])

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
