import type { FootfallCategory } from '@/types'
import { CATEGORY } from '@/utils/category'

export function CategoryDot({ category, className = '' }: { category: FootfallCategory; className?: string }) {
  return <span className={`inline-block size-2.5 shrink-0 rounded-full ${CATEGORY[category].dot} ${className}`} />
}

export function CategoryBadge({ category }: { category: FootfallCategory }) {
  const c = CATEGORY[category]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${c.badge}`}
    >
      <CategoryDot category={category} className="size-1.5" />
      {category}
    </span>
  )
}
