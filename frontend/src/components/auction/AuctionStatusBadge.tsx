import type { AuctionStatus } from '@/types'

const STYLE: Record<AuctionStatus, { label: string; className: string; dot: string }> = {
  LIVE: { label: 'Live', className: 'bg-emerald-50 text-emerald-800 ring-emerald-200', dot: 'bg-emerald-500 animate-pulse' },
  SCHEDULED: { label: 'Scheduled', className: 'bg-sky-50 text-sky-800 ring-sky-200', dot: 'bg-sky-500' },
  COMPLETED: { label: 'Completed', className: 'bg-slate-100 text-slate-700 ring-slate-200', dot: 'bg-slate-400' },
  CANCELLED: { label: 'Cancelled', className: 'bg-slate-100 text-slate-500 ring-slate-200', dot: 'bg-slate-300' },
}

export function AuctionStatusBadge({ status }: { status: AuctionStatus }) {
  const s = STYLE[status]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${s.className}`}>
      <span className={`size-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  )
}
